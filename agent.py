"""
Video AI Bot — LiveKit Agents worker.

Connects to the LiveKit server and handles AI voice sessions:
    User audio → Deepgram STT → LLM → ElevenLabs TTS → LiveKit room
    + optional LiveAvatar for a talking avatar video track

Run:
    python agent.py dev      # development (auto-reload)
    python agent.py start    # production

Env vars:
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    LLM_PROVIDER             openai | anthropic | gemini (default: openai)
    OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY
    DEEPGRAM_API_KEY
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL
    SYSTEM_PROMPT            (optional)
    LIVEAVATAR_API_KEY       (optional — enables talking avatar)
    LIVEAVATAR_AVATAR_ID     (optional — required if LIVEAVATAR_API_KEY is set)
"""
import os
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent

load_dotenv()


class VideoAIBot(Agent):
    def __init__(self):
        super().__init__(
            instructions=os.getenv(
                "SYSTEM_PROMPT",
                "You are a helpful AI assistant on a video call. Be concise and conversational.",
            )
        )


def _get_llm():
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "anthropic":
        from livekit.plugins import anthropic
        return anthropic.LLM(model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6"))
    if provider == "gemini":
        from livekit.plugins import google
        return google.LLM(model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro"))
    from livekit.plugins import openai
    return openai.LLM(model=os.getenv("OPENAI_MODEL", "gpt-4o"))


server = AgentServer()


@server.rtc_session(agent_name="video-ai-bot")
async def session_handler(ctx: agents.JobContext):
    from livekit.plugins import deepgram, elevenlabs

    session = AgentSession(
        stt=deepgram.STT(
            model="nova-2",
            language="en-US",
        ),
        llm=_get_llm(),
        tts=elevenlabs.TTS(
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "Rachel"),
            model=os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5"),
        ),
    )

    avatar_id = os.getenv("LIVEAVATAR_AVATAR_ID")
    if avatar_id:
        from livekit.plugins import liveavatar
        avatar = liveavatar.AvatarSession(avatar_id=avatar_id)
        await avatar.start(session, room=ctx.room)
        print(f"[avatar] started avatar session: {avatar_id}")

    await session.start(ctx.room, agent=VideoAIBot())
    print(f"[agent] session started in room: {ctx.room.name}")


if __name__ == "__main__":
    agents.cli.run_app(server)
