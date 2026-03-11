# video-ai-bot

A real-time AI video call bot. Users open a link in their browser, start a video call, and have a two-way conversation with an AI — the AI can hear and see them, and responds with a synthesized voice (and optionally a talking avatar).

Designed to be **model-agnostic**: swap in OpenAI, Anthropic, Google, or any other LLM provider.

---

## Architecture Overview

```
User browser (camera + mic)
    ↕ WebRTC (Daily.co)
Server bot participant (daily-python)
    ├── Audio → Deepgram STT → LLM → ElevenLabs TTS → Audio out
    └── Video frames → LLM Vision (optional)
```

For outbound calls (calling a phone number):

```
Server → Twilio PSTN → User's phone
    ↕ audio bridge
Server bot participant (daily-python room)
    └── same STT → LLM → TTS pipeline
```

---

## Approaches Considered

Three paths were evaluated for adding real-time video/voice AI:

### 1. Daily.co (Recommended)

Use Daily.co as WebRTC infrastructure. The `daily-python` SDK lets a server process join a room as a first-class participant — receiving raw PCM audio, pushing audio back, and capturing video frames. No virtual devices, no UI automation.

**Stack:** Daily.co (browser + `daily-python`) + Deepgram (STT) + LLM API + ElevenLabs (TTS)

| Pros | Cons |
|---|---|
| Server-side bot SDK — bot joins as a real participant | New vendor |
| Prebuilt browser UI (embed in one line) | `daily-python` SDK is relatively new |
| Raw audio access makes STT straightforward | Users go to your URL, not an existing app |
| Generous free tier | |
| Low operational complexity | |

---

### 2. Twilio Video

Replace TwiML voice with Twilio Video Rooms. Build a browser frontend using the Twilio Video JS SDK. The server mints JWT Access Tokens. Audio must be handled manually — Twilio Video has no built-in STT.

**Stack:** Twilio Video JS SDK (browser) + Twilio REST API (room/token) + Deepgram (STT) + LLM API + ElevenLabs (TTS)

| Pros | Cons |
|---|---|
| Stays within Twilio (one vendor) | No server-side bot participant SDK |
| Well-documented | More frontend work |
| | No prebuilt UI |

---

### 3. Xvfb + Desktop App

Run an existing video call app (Zoom, Telegram) on the server with a virtual display (`Xvfb`), virtual camera (`v4l2loopback`), and virtual audio (PulseAudio). Automate the UI to join calls and route audio through the STT/TTS pipeline.

**Stack:** Xvfb + v4l2loopback + PulseAudio + Zoom/Telegram + UI automation (`xdotool`/`pyautogui`)

| Pros | Cons |
|---|---|
| Works with existing platforms — users call on Zoom/Telegram | UI automation is fragile (app updates break it) |
| No custom frontend needed | Against ToS for most platforms |
| | Significant system-level setup |
| | High operational complexity |

---

### Comparison

| | Daily.co | Twilio Video | Xvfb + Desktop App |
|---|---|---|---|
| Server-side bot SDK | Yes (`daily-python`) | No | N/A (UI automation) |
| Prebuilt browser UI | Yes | No | N/A |
| Works with Zoom/Telegram | No | No | Yes |
| Custom frontend required | Minimal | Yes | No |
| Virtual devices needed | No | No | Yes |
| ToS risk | Low | Low | High |
| Operational complexity | Low | Medium | High |
| **Recommended** | **Yes** | — | No |

**Daily.co is the recommended path.**

---

## Hybrid: Twilio PSTN + Daily.co

For outbound calls where the user just has a phone (no browser/app needed):

1. Bot dials the user's phone number via Twilio PSTN
2. Twilio bridges the call audio into a Daily.co room
3. The Daily.co bot participant receives and sends audio normally
4. The STT → LLM → TTS pipeline is identical to the browser flow
5. Users with a browser can optionally join the same room for video

This way users need nothing but a phone, and the system stays model-agnostic.

---

## Avatar Services (Optional)

These services render a real-time talking avatar from text/audio. They are **not video call platforms** — they stream avatar video that the bot publishes as its video track.

> **⚠️ Note:** HeyGen's original Interactive Avatar API is being **sunset on March 31, 2026**. HeyGen has migrated to a new product called [LiveAvatar](https://www.liveavatar.com/). All recommendations below reflect the current landscape.

### WebRTC Platform Dependency

All modern avatar services use **LiveKit** as their WebRTC transport. This has an important architectural implication: if you want a talking avatar, you should **switch from Daily.co to LiveKit** as the WebRTC layer. LiveKit:

- Is open source and free to self-host
- Has a Python Agents framework purpose-built for voice/video AI bots
- Supports 11 avatar providers natively via plugins
- Replaces `daily-python` with equivalent capabilities

The STT (Deepgram), LLM, and TTS (ElevenLabs) modules are all first-class LiveKit Agents plugins — minimal changes needed to the existing pipeline.

### Provider Comparison

| | LiveAvatar (HeyGen) | Tavus | Simli | D-ID |
|---|---|---|---|---|
| Real-time streaming | Yes (LiveKit) | Yes (LiveKit) | Yes (LiveKit) | Yes (WebRTC) |
| Latency | ~1s | ~2s | ~300ms | ~2–3s |
| Avatar quality | Excellent | Excellent | Good (3D neural) | Good |
| Custom avatar: photo | No | No | Yes | Yes |
| Custom avatar: video | Yes (~2 min recording) | Yes (~2 min, Replica) | No | Yes |
| Voice cloning | Yes | Auto from video | Separate | Yes |
| Bring your own LLM | Yes (Lite mode) | Limited | Yes | Yes |
| Bring your own TTS | Yes (Lite mode) | No | Yes | Yes |
| Bring your own STT | Yes (Lite mode) | No | Yes | Yes |
| LiveKit Python plugin | Yes | Yes | Yes | No |
| Flexibility | High | Low | High | High |
| Cost | Mid | High | Mid | Mid |
| **Recommended** | **Yes** | — | Alt (lowest latency) | — |

### LiveAvatar Modes

LiveAvatar supports three modes. The mode affects who handles TTS — and therefore whether the avatar speaks with a generic ElevenLabs voice or its own cloned voice:

| Mode | STT | LLM | TTS | Avatar voice |
|---|---|---|---|---|
| **LITE** | You (Deepgram) | You | You (ElevenLabs) | Generic (mismatch) |
| **FULL** | LiveAvatar | LiveAvatar | LiveAvatar | Cloned ✓ |
| **CUSTOM** | You (Deepgram) | You | LiveAvatar | Cloned ✓ |

**CUSTOM mode is recommended** for this project: you keep full control of STT and LLM, but LiveAvatar handles TTS using the voice cloned from your avatar's source video. This eliminates the male avatar / female voice mismatch.

**[LiveAvatar Lite mode](https://docs.liveavatar.com/docs/custom-mode-life-cycle)** is the current implementation (Stage 9 below). Simpler to set up but uses ElevenLabs for TTS — voice may not match the avatar.

**[Simli](https://www.simli.com/)** is the best alternative if latency is critical (~300ms vs ~1s): 3D neural face rendering (not video-based lip-sync), accepts a photo to create your avatar face.

**[Tavus](https://www.tavus.io/)** manages the full conversation loop (LLM + TTS included), which is simpler to start but sacrifices control over the AI pipeline.

Without an avatar service, the bot responds with audio only (no video presence) — this is simpler and recommended for a first version.

---

## LLM Integration (Model-Agnostic)

The bot is designed so the LLM layer is swappable. Define a simple interface:

```python
class LLMProvider:
    def chat(self, messages: list[dict], stream: bool = False):
        raise NotImplementedError
```

Implementations:

```python
# OpenAI
from openai import OpenAI
class OpenAIProvider(LLMProvider):
    def __init__(self): self.client = OpenAI()
    def chat(self, messages, stream=False):
        return self.client.chat.completions.create(
            model="gpt-4o", messages=messages, stream=stream
        )

# Anthropic
import anthropic
class AnthropicProvider(LLMProvider):
    def __init__(self): self.client = anthropic.Anthropic()
    def chat(self, messages, stream=False):
        return self.client.messages.create(
            model="claude-opus-4-6", messages=messages, max_tokens=1024, stream=stream
        )

# Google
import google.generativeai as genai
class GeminiProvider(LLMProvider):
    def __init__(self): self.model = genai.GenerativeModel("gemini-1.5-pro")
    def chat(self, messages, stream=False):
        return self.model.generate_content(messages, stream=stream)
```

Set the provider via environment variable:

```bash
LLM_PROVIDER=openai   # or: anthropic, gemini
```

---

## Implementation Plan (Daily.co)

### Stage 1 — Account & Dependencies

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

### Stage 2 — Room Creation Endpoint

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

### Stage 3 — Browser Frontend

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

### Stage 4 — Bot Joins the Room

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

### Stage 5 — STT with Deepgram

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

### Stage 6 — LLM Response

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

### Stage 7 — TTS → Bot Speaks

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

### Stage 8 — Video Frame Capture (Optional)

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

### Stage 9 — Talking Avatar (Optional)

> **⚠️ Prerequisite:** This stage requires migrating from Daily.co to **LiveKit** (see Avatar Services section above). All real-time avatar services use LiveKit as their WebRTC transport.

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

### Stage 9b — Avatar with Cloned Voice (CUSTOM mode)

> **Prerequisite:** Stage 9 must be complete (LiveKit migration done). This replaces the ElevenLabs TTS plugin with LiveAvatar's built-in cloned voice.

The current Stage 9 (Lite mode) passes ElevenLabs audio to LiveAvatar for lip-sync. This causes a voice/avatar mismatch if the ElevenLabs voice doesn't match the avatar's gender/persona. CUSTOM mode fixes this: LiveAvatar renders TTS using the voice cloned from the avatar's source video.

#### Architecture

```
User browser ←→ Our LiveKit room (WebRTC)
                        ↑
LiveAvatar ─────────────┘  joins our room in CUSTOM mode
                           publishes: avatar video + cloned-voice audio
                           subscribes to: agent-control data channel

Our backend (agent.py)
  ├── subscribes to user audio → Deepgram STT → transcript
  ├── transcript → LLM → response text
  └── response text → publishes avatar.speak_text to agent-control data channel
                           ↑ LiveAvatar receives this and speaks with cloned voice
```

Key insight: LiveAvatar joins **our** LiveKit room (we provide our own `LIVEKIT_URL` + room credentials). We generate all participant tokens ourselves, so the backend can also join the room with full permissions to publish data channel events.

#### LiveAvatar Event Protocol

Events are exchanged via LiveKit data channels (JSON payloads):

| Direction | Topic | Event type | Payload |
|---|---|---|---|
| Backend → LiveAvatar | `agent-control` | `avatar.speak_text` | `{"text": "..."}` |
| Backend → LiveAvatar | `agent-control` | `avatar.interrupt` | — |
| Backend → LiveAvatar | `agent-control` | `avatar.start_listening` | — |
| Backend → LiveAvatar | `agent-control` | `avatar.stop_listening` | — |
| LiveAvatar → Backend | `agent-response` | `user.transcription` | `{"text": "..."}` |
| LiveAvatar → Backend | `agent-response` | `avatar.speak_started` | — |
| LiveAvatar → Backend | `agent-response` | `avatar.speak_ended` | — |
| LiveAvatar → Backend | `agent-response` | `session.stopped` | `{"end_reason": "..."}` |

> In CUSTOM mode our backend handles STT (Deepgram), so `user.transcription` events from LiveAvatar are not used — we generate our own transcripts.

#### Step 1 — Create LiveAvatar CUSTOM Session (in `bot.py`)

When a new room is created, call the LiveAvatar REST API to create a CUSTOM mode session pointing at our LiveKit room. LiveAvatar will join the room as a participant and publish avatar video + cloned-voice audio.

```python
import requests

def _liveavatar_join_room(room_name: str):
    """Tell LiveAvatar to join our LiveKit room in CUSTOM mode."""
    api_key = os.getenv("LIVEAVATAR_API_KEY")
    avatar_id = os.getenv("LIVEAVATAR_AVATAR_ID")
    voice_id = os.getenv("LIVEAVATAR_VOICE_ID")  # cloned voice ID from liveavatar.com

    # Generate a LiveKit token for LiveAvatar to join as a participant
    from livekit.api import AccessToken, VideoGrants
    avatar_token = (
        AccessToken(
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
        )
        .with_identity("liveavatar-bot")
        .with_name("Avatar")
        .with_grants(VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )

    # Step 1: Create session token
    r = requests.post(
        "https://api.liveavatar.com/v1/sessions/token",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={
            "mode": "CUSTOM",
            "avatar_id": avatar_id,
            "avatar_persona": {"voice_id": voice_id, "language": "en"},
            "livekit_config": {
                "url": os.getenv("LIVEKIT_URL"),
                "room_name": room_name,
                "token": avatar_token,
            },
        },
    )
    session = r.json()["data"]

    # Step 2: Start session (LiveAvatar connects to our room)
    requests.post(
        "https://api.liveavatar.com/v1/sessions/start",
        headers={"Authorization": f"Bearer {session['session_token']}"},
    )
    return session["session_id"]
```

Call `_liveavatar_join_room(room_name)` inside `get_token()` after creating the room, before dispatching the agent.

#### Step 2 — Replace ElevenLabs TTS with Data Channel Events (in `agent.py`)

Remove `elevenlabs.TTS` from `AgentSession`. Instead, after the LLM produces a response, publish an `avatar.speak_text` event to the `agent-control` data channel. LiveAvatar receives this and speaks with the cloned voice.

```python
import json
from livekit.plugins import deepgram

@server.rtc_session(agent_name="video-ai-bot")
async def session_handler(ctx: agents.JobContext):
    await ctx.connect()
    participant = await ctx.wait_for_participant()

    # No TTS plugin — LiveAvatar handles audio output
    session = AgentSession(
        stt=deepgram.STT(model="nova-2", language="en-US"),
        llm=_get_llm(),
        # tts= removed; LiveAvatar publishes cloned-voice audio directly
    )

    # Hook: intercept each reply and forward text to LiveAvatar via data channel
    @session.on("agent_speech_committed")
    async def on_speech(ev):
        payload = json.dumps({
            "event_type": "avatar.speak_text",
            "text": ev.text,
        }).encode()
        await ctx.room.local_participant.publish_data(
            payload, topic="agent-control", reliable=True
        )

    await session.start(VideoAIBot(), room=ctx.room)
    await session.generate_reply(
        instructions="Greet the user and let them know you're ready to chat."
    )
```

> **Note:** The exact `AgentSession` event name for intercepting committed speech (`agent_speech_committed`) should be verified against the current `livekit-agents` API. Alternatives: subclass `Agent` and override `on_reply`, or use `session.on("agent_reply")`.

#### Step 3 — New Environment Variables

```
LIVEAVATAR_VOICE_ID=<voice_id>   # cloned voice ID from liveavatar.com/voices
```

Find your voice ID in the LiveAvatar dashboard after creating your avatar. The avatar creation (~2-min video upload) automatically clones the voice — the resulting voice ID is listed under Voices.

#### Step 4 — Remove ElevenLabs Dependency

```bash
pip uninstall livekit-plugins-elevenlabs
# remove from requirements.txt
```

Remove `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL` from `.env`.

#### Outcome

The avatar speaks with the voice cloned from your source video. No ElevenLabs dependency. Voice and face match by construction.

---

### Stage 10 — Outbound Calls via Twilio (Optional)

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

### Stage 11 — Polish

- Streaming TTS: stream ElevenLabs audio as LLM responds chunk-by-chunk to reduce latency
- Thinking indicator: send a WebSocket message to the browser when LLM is processing; show a spinner
- Room cleanup: call `client.leave()` on `participant-left` event; delete the Daily room via REST API
- Error handling: reconnect on dropped STT connection; handle LLM rate limits

**Outcome:** Low-latency, polished video call experience.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DAILY_API_KEY` | Yes | Daily.co API key |
| `DEEPGRAM_API_KEY` | Yes | Deepgram STT API key |
| `ELEVENLABS_API_KEY` | Yes | ElevenLabs TTS API key |
| `LLM_PROVIDER` | Yes | `openai`, `anthropic`, or `gemini` |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Anthropic API key |
| `GOOGLE_API_KEY` | If using Gemini | Google AI API key |
| `TWILIO_ACCOUNT_SID` | For outbound calls | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | For outbound calls | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | For outbound calls | Twilio phone number |
| `LIVEKIT_URL` | For avatar (Stage 9+) | LiveKit server WebSocket URL |
| `LIVEKIT_API_KEY` | For avatar (Stage 9+) | LiveKit API key |
| `LIVEKIT_API_SECRET` | For avatar (Stage 9+) | LiveKit API secret |
| `LIVEAVATAR_API_KEY` | For avatar | LiveAvatar (HeyGen) API key |
| `LIVEAVATAR_AVATAR_ID` | For avatar | Your custom avatar ID from liveavatar.com |
| `LIVEAVATAR_VOICE_ID` | For Stage 9b (CUSTOM mode) | Cloned voice ID from liveavatar.com/voices |
| `PUBLIC_URL` | For outbound calls | Publicly accessible server URL |

---

## Project Structure (Planned)

```
video-ai-bot/
├── bot.py              # Main server (Flask + Daily bot participant)
├── llm.py              # Model-agnostic LLM provider interface
├── stt.py              # Deepgram STT streaming
├── tts.py              # ElevenLabs TTS
├── avatar.py           # LiveAvatar Lite mode integration (optional, requires LiveKit migration)
├── twilio_bridge.py    # Twilio PSTN ↔ Daily audio bridge (optional)
├── static/
│   └── index.html      # Browser frontend
├── .env.example        # Environment variable template
└── requirements.txt    # Python dependencies
```

> **Note (Stage 9+):** Adding a talking avatar requires migrating from `daily-python` to `livekit-agents`. The `bot.py` and frontend would be replaced; `llm.py`, `stt.py`, and `tts.py` stay largely intact as LiveKit Agents uses the same underlying SDKs.
