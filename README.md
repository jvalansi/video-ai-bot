# video-ai-bot

A real-time AI video call bot. Users open a link in their browser, start a video call, and have a two-way conversation with an AI — the AI can hear and see them, and responds with a synthesized voice (and optionally a talking avatar).

Designed to be **model-agnostic**: swap in OpenAI, Anthropic, Google, or any other LLM provider.

---

## Docs

- [Architecture](docs/architecture.md) — WebRTC approach comparison, hybrid PSTN setup
- [Avatar Services](docs/avatar.md) — LiveAvatar, Simli, Tavus, D-ID; LITE vs CUSTOM mode; voice cloning
- [LLM Integration](docs/llm.md) — Swappable provider interface (OpenAI / Anthropic / Gemini)
- [Implementation Plan](docs/implementation.md) — Stage-by-stage build guide (Stages 1–11)
- [Environment Variables](docs/env.md) — All env vars and mode detection logic

---

## Quick Start

```
DAILY_API_KEY=...
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...
LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

```bash
pip install -r requirements.txt
python bot.py        # web server
python agent.py dev  # AI pipeline (separate terminal)
```

Open `http://localhost:5000`, click **Start Call**.

---

## Stack

| Layer | Default | Alternatives |
|---|---|---|
| WebRTC | LiveKit | Daily.co (no avatar) |
| STT | Deepgram nova-2 | — |
| LLM | OpenAI gpt-4o | Anthropic, Gemini |
| TTS | ElevenLabs (LITE) / LiveAvatar cloned voice (CUSTOM) | — |
| Avatar | LiveAvatar (HeyGen) | Simli, Tavus, D-ID |

---

## Roadmap to Profitability

**The idea:** A platform to create interactive AI avatars of real people — using their voice, likeness, and knowledge. Two core use cases:
- **Personal:** simulate a deceased parent or loved one so family can still "talk" to them
- **Public figures:** talk to Einstein, Kim Kardashian, historical leaders — Wikipedia + recordings ingested as context

| Milestone | Description | Expected Monthly ROI |
|---|---|---|
| **Public figure MVP** | Einstein demo: Wikipedia RAG + voice clone + avatar, shareable link | viral/demo |
| **Freemium launch** | Free (limited public figures) + $20–50/mo personal tier | $200–500/mo |
| **Personal tier** | Upload recordings/photos of a loved one, build private avatar | high emotional value |
| **Viral loop** | Shareable conversation clips, social hooks | organic growth |

**Next step (Notion task):** Build Einstein demo — ingest Wikipedia as RAG context, clone voice from archive recordings, ship as a shareable link.

**Notion project page:** [video-ai-bot — Strategy & Profitability](https://www.notion.so/video-ai-bot-Strategy-Profitability-32505a1b5e01818795b3e24dca1066da)

---

## Project Structure

```
video-ai-bot/
├── bot.py              # Flask server — token generation, LiveAvatar session init
├── agent.py            # LiveKit Agents worker — STT → LLM → TTS/avatar pipeline
├── static/
│   └── index.html      # Browser frontend (LiveKit prebuilt UI)
├── docs/               # Extended documentation
├── requirements.txt
└── .env
```
