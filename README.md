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

These services render a real-time talking avatar from text/audio. They are **not video call platforms** — they generate a video stream that the bot pushes into the Daily.co room as its video track. All three support custom avatars.

| | HeyGen | D-ID | Tavus |
|---|---|---|---|
| Real-time streaming | Yes | Yes | Yes |
| Latency | ~1–2s | ~2–3s | ~2s |
| Avatar quality | Excellent | Good | Excellent |
| Custom avatar: photo | No | Yes | No |
| Custom avatar: video | Yes (Instant/Studio) | Yes | Yes (Replica) |
| Voice cloning | Yes | Yes | Yes (auto from video) |
| Bring your own LLM | Yes | Yes | Limited |
| Full conversation loop managed | No | No (yes w/ Agents add-on) | Yes |
| Flexibility | High | High | Low |
| Cost | Mid | Mid | High |
| **Recommended** | **Yes** | — | — |

**HeyGen** is recommended: best quality, lowest latency (~1–2s), real-time streaming API, flexible custom avatar options, and lets you bring your own LLM.
**Tavus CVI** is an alternative if you want a fully managed conversation loop with less control.

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

Integrate HeyGen's Streaming Avatar API to give the bot a visual presence. The bot streams HeyGen avatar video into the Daily room as its video track.

```python
# Initialize HeyGen streaming session
heygen_session = requests.post(
    "https://api.heygen.com/v1/streaming.new",
    headers={"X-Api-Key": os.getenv("HEYGEN_API_KEY")},
    json={"quality": "medium", "avatar_name": "your_avatar_id"}
)

# Send text to animate
def speak_with_avatar(text):
    requests.post(
        "https://api.heygen.com/v1/streaming.task",
        headers={"X-Api-Key": os.getenv("HEYGEN_API_KEY")},
        json={"session_id": session_id, "text": text, "task_type": "talk"}
    )
    # HeyGen returns a video stream → push into Daily room as bot's video track
```

**Outcome:** The bot has a face. Users see a talking avatar that lip-syncs to the LLM's responses.

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
| `HEYGEN_API_KEY` | For avatar | HeyGen API key |
| `PUBLIC_URL` | For outbound calls | Publicly accessible server URL |

---

## Project Structure (Planned)

```
video-ai-bot/
├── bot.py              # Main server (Flask + Daily bot participant)
├── llm.py              # Model-agnostic LLM provider interface
├── stt.py              # Deepgram STT streaming
├── tts.py              # ElevenLabs TTS
├── avatar.py           # HeyGen avatar integration (optional)
├── twilio_bridge.py    # Twilio PSTN ↔ Daily audio bridge (optional)
├── static/
│   └── index.html      # Browser frontend
├── .env.example        # Environment variable template
└── requirements.txt    # Python dependencies
```
