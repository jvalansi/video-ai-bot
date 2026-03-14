"""
Video AI Bot — LiveKit Agents worker.

Two avatar modes are supported (set by which env vars are present):

  LITE mode  (LIVEAVATAR_API_KEY set, LIVEAVATAR_VOICE_ID not set):
    User audio → Deepgram STT → LLM → ElevenLabs TTS → LiveKit room
    LiveAvatar lip-syncs avatar video to the ElevenLabs audio.

  CUSTOM mode  (LIVEAVATAR_API_KEY + LIVEAVATAR_VOICE_ID both set):
    User audio → Deepgram STT → LLM → avatar.speak_text data channel event
    LiveAvatar renders TTS using the avatar's cloned voice (no ElevenLabs).
    bot.py has already told LiveAvatar to join the room before this agent runs.

Run:
    python agent.py dev      # development (auto-reload)
    python agent.py start    # production

Env vars:
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    LLM_PROVIDER             openai | anthropic | gemini (default: openai)
    OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY
    DEEPGRAM_API_KEY
    SYSTEM_PROMPT            (optional)
    LIVEAVATAR_API_KEY       (optional — enables talking avatar)
    LIVEAVATAR_AVATAR_ID     (optional — required if LIVEAVATAR_API_KEY is set)
    LIVEAVATAR_VOICE_ID      (optional — enables CUSTOM mode with cloned voice)
    ELEVENLABS_API_KEY       (LITE mode only)
    ELEVENLABS_VOICE_ID      (LITE mode only, default: Rachel)
    ELEVENLABS_MODEL         (LITE mode only, default: eleven_turbo_v2_5)
"""
import json
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


def _is_custom_mode() -> bool:
    """CUSTOM mode = LiveAvatar handles TTS with cloned voice (no ElevenLabs)."""
    return bool(os.getenv("LIVEAVATAR_API_KEY") and os.getenv("LIVEAVATAR_VOICE_ID"))


async def _wait_for_human_participant(ctx: agents.JobContext):
    """Return the first non-avatar remote participant."""
    import asyncio
    # Check already-present participants first
    for p in ctx.room.remote_participants.values():
        if p.identity != "liveavatar-bot":
            return p
    # None found yet — wait for one to arrive
    fut: asyncio.Future = asyncio.get_event_loop().create_future()

    def _on_connected(p):
        if p.identity != "liveavatar-bot" and not fut.done():
            fut.set_result(p)

    ctx.room.on("participant_connected", _on_connected)
    try:
        return await fut
    finally:
        ctx.room.off("participant_connected", _on_connected)


@server.rtc_session(agent_name="video-ai-bot")
async def session_handler(ctx: agents.JobContext):
    from livekit.plugins import deepgram

    await ctx.connect()
    participant = await _wait_for_human_participant(ctx)
    print(f"[agent] participant joined: {participant.identity}")

    if _is_custom_mode():
        # CUSTOM mode: LiveAvatar joined the room (via bot.py) and handles TTS
        # with the avatar's cloned voice. We handle STT + LLM only.
        print("[agent] CUSTOM mode — LiveAvatar handles TTS with cloned voice")
        session = AgentSession(
            stt=deepgram.STT(model="nova-2", language="en-US"),
            llm=_get_llm(),
        )

        # Forward each committed reply as an avatar.speak_text data channel event.
        # LiveAvatar receives this on the agent-control topic and speaks with
        # the cloned voice.
        @session.on("agent_speech_committed")
        async def _on_speech(ev):
            payload = json.dumps(
                {"event_type": "avatar.speak_text", "text": ev.text}
            ).encode()
            await ctx.room.local_participant.publish_data(
                payload, topic="agent-control", reliable=True
            )

        await session.start(VideoAIBot(), room=ctx.room)

    else:
        # LITE mode: ElevenLabs TTS drives audio; LiveAvatar (if configured)
        # lip-syncs the avatar to that audio.
        from livekit.plugins import elevenlabs

        session = AgentSession(
            stt=deepgram.STT(model="nova-2", language="en-US"),
            llm=_get_llm(),
            tts=elevenlabs.TTS(
                api_key=os.getenv("ELEVENLABS_API_KEY"),
                voice_id=os.getenv("ELEVENLABS_VOICE_ID", "Adam"),
                model=os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5"),
            ),
        )

        avatar_id = os.getenv("LIVEAVATAR_AVATAR_ID")
        if avatar_id:
            try:
                from livekit.plugins import liveavatar
                avatar = liveavatar.AvatarSession(avatar_id=avatar_id)
                await avatar.start(session, room=ctx.room)
                print(f"[avatar] LITE mode avatar session started: {avatar_id}")
            except Exception as e:
                print(f"[avatar] failed to start (falling back to audio-only): {e}")

        await session.start(VideoAIBot(), room=ctx.room)

    print(f"[agent] session started in room: {ctx.room.name}")
    await session.generate_reply(instructions="Greet the user and let them know you're ready to chat.")


if __name__ == "__main__":
    agents.cli.run_app(server)
