# Implementation Plan

> The bot is built in stages. Each stage is independently shippable. Start with Stage 1–7 for a working voice bot, then add stages as needed.

---

## Stage 1 — Account & Dependencies

1. Create a [Daily.co](https://daily.co) account, create an app, note the **API key**
2. Sign up for [Deepgram](https://deepgram.com) (STT) and [ElevenLabs](https://elevenlabs.io) (TTS)
3. Add keys to `.env`:
   ```
   DAILY_API_KEY=...
   DEEPGRAM_API_KEY=...
   ELEVENLABS_API_KEY=...
   LLM_PROVIDER=openai   # or anthropic, gemini
   OPENAI_API_KEY=...    # whichever provider you choose
   ```
4. Install dependencies:
   ```bash
   pip install daily-python deepgram-sdk elevenlabs openai flask python-dotenv
   ```

**Outcome:** API keys in place, packages installed.

---

## Stage 2 — Room Creation Endpoint

Add `POST /room` to the server — creates a Daily room on demand and returns its URL.

```python
@app.route("/room", methods=["POST"])
def create_room():
    resp = requests.post(
        "https://api.daily.co/v1/rooms",
        headers={"Authorization": f"Bearer {os.getenv('DAILY_API_KEY')}"},
        json={"properties": {"max_participants": 2}}
    )
    room = resp.json()
    return jsonify({"url": room["url"], "name": room["name"]})
```

**Outcome:** `POST /room` creates a fresh Daily room and returns its URL.

---

## Stage 3 — Browser Frontend

A minimal `static/index.html` that embeds the Daily Prebuilt UI — no custom WebRTC code needed.

```html
<!DOCTYPE html>
<html>
<body>
  <button id="start">Start Call</button>
  <div id="call" style="display:none; width:100%; height:600px;"></div>
  <script src="https://unpkg.com/@daily-co/daily-js"></script>
  <script>
    document.getElementById("start").onclick = async () => {
      const { url } = await fetch("/room", { method: "POST" }).then(r => r.json());
      document.getElementById("start").style.display = "none";
      document.getElementById("call").style.display = "block";
      const call = window.DailyIframe.createFrame(document.getElementById("call"));
      await call.join({ url });
    };
  </script>
</body>
</html>
```

**Outcome:** User opens the page, clicks "Start Call", and is in a Daily video room. The bot is not there yet, but the room works.

---

## Stage 4 — Bot Joins the Room

When a room is created, the server also joins it as a bot participant via `daily-python`. The bot subscribes to the user's audio.

```python
from daily import Daily, CallClient

def start_bot(room_url):
    Daily.init()
    client = CallClient()
    client.join(room_url, client_settings={
        "inputs": {"camera": False, "microphone": False}
    })
    client.set_audio_renderer(on_audio_frame, audio_source="remote")
```

**Outcome:** When a room is created, the bot joins server-side and starts receiving audio. The user sees a second (bot) participant.

---

## Stage 5 — STT with Deepgram

Pipe raw PCM audio frames from the bot into Deepgram's streaming STT. Deepgram's built-in endpointing handles VAD (no separate library needed).

```python
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

dg = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))
conn = dg.listen.live.v("1")
conn.on(LiveTranscriptionEvents.Transcript, on_transcript)
conn.start(LiveOptions(model="nova-2", endpointing=500))

def on_audio_frame(frames, *args):
    conn.send(frames)

def on_transcript(self, result, **kwargs):
    text = result.channel.alternatives[0].transcript
    if result.is_final and text:
        handle_turn(text)
```

**Outcome:** When the user speaks, `handle_turn(text)` is called with the transcribed speech.

---

## Stage 6 — LLM Response

Call the configured LLM provider with the conversation history. Maintain history across turns for context.

```python
history = []

def handle_turn(transcript):
    history.append({"role": "user", "content": transcript})
    llm = get_provider()  # returns OpenAIProvider, AnthropicProvider, etc.
    response_text = llm.chat(history)
    history.append({"role": "assistant", "content": response_text})
    speak(response_text)
```

**Outcome:** The LLM responds contextually to the user's speech. Swap providers via `LLM_PROVIDER` env var.

---

## Stage 7 — TTS → Bot Speaks

Convert the LLM's text response to audio and push it back into the Daily room through the bot participant.

```python
from elevenlabs.client import ElevenLabs

el = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

def speak(text):
    audio = el.generate(text=text, voice="Rachel", model="eleven_monolingual_v1")
    bot_client.send_audio(audio)  # pushes PCM into the Daily room
```

**Outcome:** Full voice loop — user speaks, bot transcribes, LLM responds, bot speaks back. Shippable v1.

---

## Stage 8 — Video Frame Capture (Optional)

Capture a frame from the user's camera when they finish speaking and include it in the LLM request for vision-capable models.

Browser (send frame at turn end):
```js
const canvas = document.createElement("canvas");
canvas.drawImage(videoElement, 0, 0);
const frame = canvas.toDataURL("image/jpeg", 0.7);
// POST frame to server alongside transcript
```

Server (include image in LLM call):
```python
history.append({"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}},
    {"type": "text", "text": transcript}
]})
```

**Outcome:** The LLM can see the user and respond to what's visible on camera.

---

## Stage 9 — Talking Avatar (Optional)

> **⚠️ Prerequisite:** This stage requires migrating from Daily.co to **LiveKit** (see [Avatar Services](avatar.md)). All real-time avatar services use LiveKit as their WebRTC transport.

Give the bot a visual presence using **LiveAvatar Lite mode** (HeyGen's new platform). The bot streams a talking avatar video into the LiveKit room as its video track. In Lite mode, you keep your own LLM, TTS, and STT — LiveAvatar only handles the avatar rendering.

**Step 1 — Create your custom avatar**

Upload a ~2-minute continuous video recording of yourself at [liveavatar.com](https://www.liveavatar.com). LiveAvatar generates a personal avatar that matches your face, expressions, and voice.

**Step 2 — Migrate to LiveKit Agents**

```bash
pip install livekit-agents livekit-plugins-deepgram livekit-plugins-elevenlabs \
            livekit-plugins-openai livekit-plugins-anthropic livekit-plugins-liveavatar
```

**Step 3 — Add avatar to the agent**

```python
from livekit import agents
from livekit.agents import AgentSession, AgentServer
from livekit.plugins import deepgram, elevenlabs, openai, liveavatar

server = AgentServer()

@server.rtc_session(agent_name="video-ai-bot")
async def my_agent(ctx: agents.JobContext):
    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o"),   # swap for anthropic.LLM() or google.LLM()
        tts=elevenlabs.TTS(voice_id="..."),
    )

    avatar = liveavatar.AvatarSession(
        api_key=os.getenv("LIVEAVATAR_API_KEY"),
        avatar_id=os.getenv("LIVEAVATAR_AVATAR_ID"),  # your custom avatar ID
    )

    await avatar.start(session, room=ctx.room)
    await session.start(ctx.room, agent=MyAgent())
```

**Outcome:** The bot has a face. Users see a talking avatar of your custom persona, lip-synced to the LLM's responses, while you retain full control over the AI pipeline.

---

## Stage 9b — Avatar with Cloned Voice (CUSTOM mode)

> **Prerequisite:** Stage 9 must be complete (LiveKit migration done). This upgrades from Lite mode (ElevenLabs voice) to CUSTOM mode (avatar's own cloned voice).

See the full plan in [Avatar Services → CUSTOM Mode](avatar.md#custom-mode-stage-9b--cloned-voice).

**Outcome:** The avatar speaks with the voice cloned from your source video. Voice and face match by construction.

---

## Stage 10 — Outbound Calls via Twilio (Optional)

Dial a user's phone number via Twilio and bridge the call into a Daily.co room. The same STT → LLM → TTS pipeline handles the call.

```python
from twilio.rest import Client as TwilioClient

twilio = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

def call_user(phone_number, room_url):
    # Create Daily room and start bot
    bot_client = start_bot(room_url)
    # Dial the user and bridge audio into the Daily room
    twilio.calls.create(
        to=phone_number,
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        url=f"{os.getenv('PUBLIC_URL')}/twiml?room={room_url}"
    )

@app.route("/twiml")
def twiml():
    # TwiML that bridges the phone call audio to Daily
    return f"""<Response>
        <Connect><Stream url="wss://yourserver/audio-bridge"/></Connect>
    </Response>"""
```

**Outcome:** The bot can initiate calls to any phone number. Users with only a phone (no browser) can participate in the conversation.

---

## Stage 11 — Polish

- Streaming TTS: stream ElevenLabs audio as LLM responds chunk-by-chunk to reduce latency
- Thinking indicator: send a WebSocket message to the browser when LLM is processing; show a spinner
- Room cleanup: call `client.leave()` on `participant-left` event; delete the Daily room via REST API
- Error handling: reconnect on dropped STT connection; handle LLM rate limits

**Outcome:** Low-latency, polished video call experience.
