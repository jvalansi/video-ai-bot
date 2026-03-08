"""
Deepgram streaming Speech-to-Text client.
Receives raw PCM audio frames and calls on_transcript when speech is detected.
"""
import os
import threading
from typing import Callable


class STTClient:
    """
    Wraps Deepgram's live transcription WebSocket.
    Call send(audio_bytes) to feed PCM audio; on_transcript is called with
    final transcripts.
    """

    def __init__(self, on_transcript: Callable[[str], None]):
        self.on_transcript = on_transcript
        self._conn = None
        self._lock = threading.Lock()

    def start(self, sample_rate: int = 16000, channels: int = 1):
        from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

        dg = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))
        conn = dg.listen.websocket.v("1")

        def on_message(self_dg, result, **kwargs):
            try:
                alt = result.channel.alternatives[0]
                if result.is_final and alt.transcript:
                    self.on_transcript(alt.transcript)
            except Exception as e:
                print(f"[STT] transcript error: {e}")

        conn.on(LiveTranscriptionEvents.Transcript, on_message)

        options = LiveOptions(
            model="nova-2",
            language="en-US",
            encoding="linear16",
            sample_rate=sample_rate,
            channels=channels,
            endpointing=500,       # ms of silence to trigger end-of-utterance
            interim_results=False,
        )
        started = conn.start(options)
        if not started:
            raise RuntimeError("Failed to start Deepgram live connection")

        with self._lock:
            self._conn = conn

        print("[STT] Deepgram connection started")

    def send(self, audio_bytes: bytes):
        with self._lock:
            if self._conn is not None:
                self._conn.send(audio_bytes)

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.finish()
                self._conn = None
        print("[STT] Deepgram connection closed")
