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

**Current state:** Working prototype — local dev, no billing, single user.

| Milestone | Description | Expected Monthly ROI |
|---|---|---|
| **Hosted deployment** | Deploy to public URL, stable infra | — |
| **Customer onboarding** | Sign-up, provision a video call room per customer | — |
| **Billing** | Per-minute or subscription ($30–100/mo) | $150–500/mo (5–10 customers) |
| **Avatar quality** | LiveAvatar / HeyGen cloned voice for premium feel | higher conversion |
| **B2B vertical** | Target customer service, coaching, tutoring use cases | $500–2k/mo/client |
| **White-label API** | Let developers embed video AI in their own products | enterprise tier |

**Next step (Notion task):** Deploy to production + add Stripe billing — ROI hypothesis $150/mo from first 5 paying customers.

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
