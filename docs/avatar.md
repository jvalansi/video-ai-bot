# Avatar Services

These services render a real-time talking avatar from text/audio. They are **not video call platforms** — they stream avatar video that the bot publishes as its video track.

> **⚠️ Note:** HeyGen's original Interactive Avatar API is being **sunset on March 31, 2026**. HeyGen has migrated to a new product called [LiveAvatar](https://www.liveavatar.com/). All recommendations below reflect the current landscape.

## WebRTC Platform Dependency

All modern avatar services use **LiveKit** as their WebRTC transport. This has an important architectural implication: if you want a talking avatar, you should **switch from Daily.co to LiveKit** as the WebRTC layer. LiveKit:

- Is open source and free to self-host
- Has a Python Agents framework purpose-built for voice/video AI bots
- Supports 11 avatar providers natively via plugins
- Replaces `daily-python` with equivalent capabilities

The STT (Deepgram), LLM, and TTS (ElevenLabs) modules are all first-class LiveKit Agents plugins — minimal changes needed to the existing pipeline.

---

## Provider Comparison

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

**[Simli](https://www.simli.com/)** is the best alternative if latency is critical (~300ms vs ~1s): 3D neural face rendering (not video-based lip-sync), accepts a photo to create your avatar face.

**[Tavus](https://www.tavus.io/)** manages the full conversation loop (LLM + TTS included), which is simpler to start but sacrifices control over the AI pipeline.

Without an avatar service, the bot responds with audio only (no video presence) — this is simpler and recommended for a first version.

---

## LiveAvatar Modes

LiveAvatar supports three modes. The mode affects who handles TTS — and therefore whether the avatar speaks with a generic ElevenLabs voice or its own cloned voice:

| Mode | STT | LLM | TTS | Avatar voice |
|---|---|---|---|---|
| **LITE** | You (Deepgram) | You | You (ElevenLabs) | Generic (mismatch possible) |
| **FULL** | LiveAvatar | LiveAvatar | LiveAvatar | Cloned ✓ |
| **CUSTOM** | You (Deepgram) | You | LiveAvatar | Cloned ✓ |

**CUSTOM mode is recommended** for this project: you keep full control of STT and LLM, but LiveAvatar handles TTS using the voice cloned from your avatar's source video. This eliminates the male avatar / female voice mismatch.

---

## LITE Mode (Stage 9 — current implementation)

You keep your own LLM, TTS (ElevenLabs), and STT (Deepgram). LiveAvatar only handles avatar rendering, lip-syncing to the ElevenLabs audio. Simpler to set up, but voice may not match the avatar's gender/persona.

See [Implementation Plan → Stage 9](implementation.md#stage-9--talking-avatar-optional).

---

## CUSTOM Mode (Stage 9b — cloned voice)

LiveAvatar joins **our** LiveKit room in CUSTOM mode and handles TTS using the voice cloned from your avatar's source video. We keep STT (Deepgram) and LLM. No ElevenLabs required.

### Architecture

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

### Event Protocol

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

### Step 1 — Create LiveAvatar CUSTOM Session (in `bot.py`)

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

### Step 2 — Replace ElevenLabs TTS with Data Channel Events (in `agent.py`)

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

### Step 3 — New Environment Variables

```
LIVEAVATAR_VOICE_ID=<voice_id>   # cloned voice ID from liveavatar.com/voices
```

Find your voice ID in the LiveAvatar dashboard after creating your avatar. The avatar creation (~2-min video upload) automatically clones the voice — the resulting voice ID is listed under Voices.

### Step 4 — Remove ElevenLabs Dependency

```bash
pip uninstall livekit-plugins-elevenlabs
# remove from requirements.txt
```

Remove `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL` from `.env`.

### Outcome

The avatar speaks with the voice cloned from your source video. No ElevenLabs dependency. Voice and face match by construction.
