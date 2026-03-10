"""
Video AI Bot — Flask web server.

Endpoints:
  GET  /        → serves static/index.html
  POST /token   → generates a LiveKit access token for the browser

The AI pipeline (STT → LLM → TTS → avatar) runs in a separate process:
    python agent.py dev
"""
import os
import uuid
from flask import Flask, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/token", methods=["POST"])
def get_token():
    """
    Generate a LiveKit access token for a new room.
    Returns: { token, room, url }
    """
    from livekit.api import AccessToken, VideoGrants

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

    return jsonify({
        "token": token,
        "room": room_name,
        "url": os.getenv("LIVEKIT_URL"),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
