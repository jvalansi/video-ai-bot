# Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DAILY_API_KEY` | Yes | Daily.co API key |
| `DEEPGRAM_API_KEY` | Yes | Deepgram STT API key |
| `ELEVENLABS_API_KEY` | Lite mode only | ElevenLabs TTS API key |
| `ELEVENLABS_VOICE_ID` | Lite mode only | ElevenLabs voice ID (default: Rachel) |
| `ELEVENLABS_MODEL` | Lite mode only | ElevenLabs model (default: eleven_turbo_v2_5) |
| `LLM_PROVIDER` | Yes | `openai`, `anthropic`, or `gemini` |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Anthropic API key |
| `GOOGLE_API_KEY` | If using Gemini | Google AI API key |
| `SYSTEM_PROMPT` | No | Custom system prompt for the AI |
| `TWILIO_ACCOUNT_SID` | For outbound calls | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | For outbound calls | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | For outbound calls | Twilio phone number |
| `PUBLIC_URL` | For outbound calls | Publicly accessible server URL |
| `LIVEKIT_URL` | For avatar (Stage 9+) | LiveKit server WebSocket URL |
| `LIVEKIT_API_KEY` | For avatar (Stage 9+) | LiveKit API key |
| `LIVEKIT_API_SECRET` | For avatar (Stage 9+) | LiveKit API secret |
| `LIVEAVATAR_API_KEY` | For avatar | LiveAvatar (HeyGen) API key |
| `LIVEAVATAR_AVATAR_ID` | For avatar | Your custom avatar ID from liveavatar.com |
| `LIVEAVATAR_VOICE_ID` | CUSTOM mode only | Cloned voice ID — enables CUSTOM mode when set |
| `PORT` | No | Flask server port (default: 5000) |

## Mode Detection

The bot automatically selects the avatar mode based on which env vars are set:

| `LIVEAVATAR_API_KEY` | `LIVEAVATAR_VOICE_ID` | Mode |
|---|---|---|
| Not set | — | Audio-only (no avatar) |
| Set | Not set | **LITE** — ElevenLabs TTS, LiveAvatar lip-syncs |
| Set | Set | **CUSTOM** — LiveAvatar cloned-voice TTS, no ElevenLabs needed |
