# Architecture

## Overview

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
