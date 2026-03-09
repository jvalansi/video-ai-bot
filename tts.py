"""
ElevenLabs Text-to-Speech client.
Returns raw 16-bit PCM audio at 16 kHz (mono) to feed directly into Daily's
virtual microphone device.
"""
import os


class TTSClient:
    def __init__(self):
        from elevenlabs.client import ElevenLabs
        self.client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.voice = os.getenv("ELEVENLABS_VOICE_ID", "Rachel")
        self.model = os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5")

    def synthesize(self, text: str) -> bytes:
        """
        Convert text to PCM audio bytes (16-bit, 16 kHz, mono).
        Returns empty bytes on failure.
        """
        try:
            audio_iter = self.client.text_to_speech.convert(
                voice_id=self.voice,
                text=text,
                model_id=self.model,
                output_format="pcm_16000",
            )
            return b"".join(audio_iter)
        except Exception as e:
            print(f"[TTS] error: {e}")
            return b""
