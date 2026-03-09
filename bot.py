"""
Video AI Bot — Flask server + Daily.co bot participant.

Endpoints:
  GET  /        → serves static/index.html
  POST /room    → creates a Daily room and starts a bot participant
  POST /call    → dials a phone number via Twilio (optional)
"""
import os
import time
import uuid
import threading
import requests
from flask import Flask, jsonify, send_from_directory, request, abort
from dotenv import load_dotenv

from llm import get_llm_provider
from stt import STTClient
from tts import TTSClient

load_dotenv()

app = Flask(__name__, static_folder="static")

# Guard Daily.init() — must be called exactly once per process
_daily_initialized = False
_daily_init_lock = threading.Lock()

# room_name -> BotParticipant
active_bots: dict[str, "BotParticipant"] = {}


def _ensure_daily_init():
    global _daily_initialized
    with _daily_init_lock:
        if not _daily_initialized:
            from daily import Daily
            Daily.init()
            _daily_initialized = True


class BotParticipant:
    """
    Server-side bot that joins a Daily room and drives a voice conversation:
        Remote audio → Deepgram STT → LLM → ElevenLabs TTS → Daily mic
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1

    def __init__(self, room_url: str, room_name: str):
        self.room_url = room_url
        self.room_name = room_name
        self.device_name = f"bot-mic-{uuid.uuid4().hex[:8]}"

        system_prompt = os.getenv(
            "SYSTEM_PROMPT",
            "You are a helpful AI assistant on a video call. Be concise and conversational.",
        )
        self.history: list[dict] = [{"role": "system", "content": system_prompt}]

        self.llm = get_llm_provider()
        self.tts = TTSClient()
        self.stt: STTClient | None = None

        self._mic_device = None
        self._daily_client = None
        self._speaking = threading.Lock()
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    # Audio renderer — called by Daily SDK from its internal thread
    # ------------------------------------------------------------------

    def _on_audio_data(self, participant_id: str, audio_data, audio_source: str):
        """Feed raw PCM bytes from remote participants into Deepgram."""
        if self.stt:
            self.stt.send(bytes(audio_data.audio_frames))

    # ------------------------------------------------------------------
    # STT transcript handler — called from Deepgram's internal thread
    # ------------------------------------------------------------------

    def _on_transcript(self, text: str):
        print(f"[{self.room_name}][STT] {text}")
        # Ignore new input while the bot is already speaking
        if self._speaking.locked():
            return
        threading.Thread(target=self._respond, args=(text,), daemon=True).start()

    # ------------------------------------------------------------------
    # LLM → TTS pipeline
    # ------------------------------------------------------------------

    def _respond(self, text: str):
        with self._speaking:
            self.history.append({"role": "user", "content": text})
            try:
                response_text = self.llm.chat(self.history)
            except Exception as e:
                print(f"[{self.room_name}][LLM] error: {e}")
                return

            print(f"[{self.room_name}][LLM] {response_text}")
            self.history.append({"role": "assistant", "content": response_text})

            audio = self.tts.synthesize(response_text)
            if audio and self._mic_device:
                try:
                    self._mic_device.write_frames(audio)
                except Exception as e:
                    print(f"[{self.room_name}][MIC] write error: {e}")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_participant_left(self, participant, reason):
        participant_id = participant.get("id", "")
        # If the local bot itself or the only remote user left, stop
        print(f"[{self.room_name}] participant left: {participant_id} ({reason})")
        # Stop when the last human leaves (any non-bot participant)
        if participant.get("info", {}).get("isLocal") is False:
            self._stop.set()

    def _on_call_state_updated(self, state):
        print(f"[{self.room_name}] call state: {state}")
        if state in ("left", "error"):
            self._stop.set()

    # ------------------------------------------------------------------
    # Main run loop (blocks until room ends)
    # ------------------------------------------------------------------

    def run(self):
        try:
            self._run()
        except Exception as e:
            import traceback
            print(f"[{self.room_name}] FATAL error in bot thread: {e}", flush=True)
            traceback.print_exc()

    def _run(self):
        _ensure_daily_init()

        from daily import CallClient, VirtualMicrophoneDevice

        # Create virtual mic for bot audio output
        from daily import Daily
        self._mic_device = Daily.create_microphone_device(
            self.device_name,
            sample_rate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
        )

        # Create Daily client with event handlers
        from daily import EventHandler

        bot_self = self

        client = self

        class BotEventHandler(EventHandler):
            def on_participant_joined(self, participant):
                pid = participant.get("id", "")
                info = participant.get("info", {})
                if not info.get("isLocal", False):
                    print(f"[{client.room_name}] remote participant joined: {pid}, registering audio renderer")
                    client._daily_client.set_audio_renderer(
                        pid,
                        client._on_audio_data,
                        audio_source="microphone",
                        sample_rate=client.SAMPLE_RATE,
                    )

            def on_participant_left(self, participant, reason):
                client._on_participant_left(participant, reason)

            def on_call_state_updated(self, state):
                client._on_call_state_updated(state)

        self._daily_client = CallClient(event_handler=BotEventHandler())

        # Start Deepgram STT
        self.stt = STTClient(on_transcript=self._on_transcript)
        self.stt.start(sample_rate=self.SAMPLE_RATE, channels=self.CHANNELS)

        # Join the Daily room
        self._daily_client.join(
            self.room_url,
            client_settings={
                "inputs": {
                    "camera": {"isEnabled": False},
                    "microphone": {
                        "isEnabled": True,
                        "settings": {"deviceId": self.device_name},
                    },
                }
            },
        )

        print(f"[{self.room_name}] bot joined")

        # Block until the room ends or the last participant leaves
        self._stop.wait()
        self._cleanup()

    def _cleanup(self):
        print(f"[{self.room_name}] cleaning up")
        if self.stt:
            self.stt.close()
        if self._daily_client:
            self._daily_client.leave()
            self._daily_client.release()
        active_bots.pop(self.room_name, None)
        self._delete_daily_room()

    def _delete_daily_room(self):
        try:
            requests.delete(
                f"https://api.daily.co/v1/rooms/{self.room_name}",
                headers={"Authorization": f"Bearer {os.getenv('DAILY_API_KEY')}"},
                timeout=5,
            )
            print(f"[{self.room_name}] room deleted")
        except Exception as e:
            print(f"[{self.room_name}] failed to delete room: {e}")


# ------------------------------------------------------------------
# Flask routes
# ------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/room", methods=["POST"])
def create_room():
    """Create a Daily room and start a bot participant in it."""
    resp = requests.post(
        "https://api.daily.co/v1/rooms",
        headers={"Authorization": f"Bearer {os.getenv('DAILY_API_KEY')}"},
        json={
            "properties": {
                "max_participants": 10,
                "exp": int(time.time()) + 3600,  # room expires in 1 hour
                "enable_prejoin_ui": False,
            }
        },
        timeout=10,
    )
    if not resp.ok:
        abort(502, description=f"Daily API error: {resp.text}")

    room = resp.json()
    room_url: str = room["url"]
    room_name: str = room["name"]

    bot = BotParticipant(room_url=room_url, room_name=room_name)
    t = threading.Thread(target=bot.run, daemon=True)
    t.start()
    active_bots[room_name] = bot

    return jsonify({"url": room_url, "name": room_name})


@app.route("/rooms", methods=["GET"])
def list_rooms():
    """Return currently active bot sessions (for debugging)."""
    return jsonify({"rooms": list(active_bots.keys())})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
