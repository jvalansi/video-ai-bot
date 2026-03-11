"""
Video AI Bot — Flask web server.

Endpoints:
  GET  /        → serves static/index.html
  POST /token   → generates a LiveKit access token for the browser

The AI pipeline (STT → LLM → TTS → avatar) runs in a separate process:
    python agent.py dev
"""
import asyncio
import os
import uuid
import requests
from flask import Flask, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static")


def _liveavatar_join_room(room_name: str) -> str | None:
    """
    Create a LiveAvatar CUSTOM mode session and tell it to join our LiveKit room.
    LiveAvatar will publish avatar video + cloned-voice audio as a participant.
    Returns the session_id, or None if LIVEAVATAR_API_KEY is not set.
    """
    api_key = os.getenv("LIVEAVATAR_API_KEY")
    avatar_id = os.getenv("LIVEAVATAR_AVATAR_ID")
    if not api_key or not avatar_id:
        return None

    from livekit.api import AccessToken, VideoGrants

    # Generate a LiveKit token for the LiveAvatar participant
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

    payload = {
        "mode": "CUSTOM",
        "avatar_id": avatar_id,
        "livekit_config": {
            "url": os.getenv("LIVEKIT_URL"),
            "room_name": room_name,
            "token": avatar_token,
        },
    }
    voice_id = os.getenv("LIVEAVATAR_VOICE_ID")
    if voice_id:
        payload["avatar_persona"] = {"voice_id": voice_id, "language": "en"}

    r = requests.post(
        "https://api.liveavatar.com/v1/sessions/token",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
    session = r.json()["data"]

    requests.post(
        "https://api.liveavatar.com/v1/sessions/start",
        headers={"Authorization": f"Bearer {session['session_token']}"},
        timeout=10,
    ).raise_for_status()

    print(f"[avatar] LiveAvatar CUSTOM session started: {session['session_id']}")
    return session["session_id"]


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/token", methods=["POST"])
def get_token():
    """
    Generate a LiveKit access token for a new room.
    Returns: { token, room, url }
    """
    from livekit.api import AccessToken, VideoGrants, LiveKitAPI
    from livekit.api.agent_dispatch_service import CreateAgentDispatchRequest

    room_name = f"room-{uuid.uuid4().hex[:8]}"

    token = (
        AccessToken(
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
        )
        .with_identity(f"user-{uuid.uuid4().hex[:6]}")
        .with_name("User")
        .with_grants(VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )

    # If CUSTOM mode avatar is configured, have LiveAvatar join the room first
    _liveavatar_join_room(room_name)

    # Dispatch the agent to the room
    async def _dispatch():
        async with LiveKitAPI() as lkapi:
            await lkapi.agent_dispatch.create_dispatch(
                CreateAgentDispatchRequest(agent_name="video-ai-bot", room=room_name)
            )

    asyncio.run(_dispatch())

    return jsonify({
        "token": token,
        "room": room_name,
        "url": os.getenv("LIVEKIT_URL"),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
