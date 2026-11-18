"""Text-to-Speech (TTS) service using edge-tts."""

import asyncio
import io
import logging
import wave
from typing import AsyncGenerator, Optional

import edge_tts
from app.core.config import settings

logger = logging.getLogger("voice.tts")


def generate_silent_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generates a brief silent WAV audio payload for offline fallback."""
    num_samples = int(duration_s * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


class EdgeTTSService:
    """Streams and synthesizes speech using Microsoft Edge TTS."""

    def __init__(self, voice: Optional[str] = None):
        self.voice = voice or getattr(settings, "TTS_VOICE", "en-IN-NeerjaNeural")

    async def stream_audio_chunks(
        self,
        text: str,
        voice: Optional[str] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> AsyncGenerator[bytes, None]:
        """Asynchronously streams MP3 audio chunks. Stops immediately if cancel_event is set."""
        if not text or not text.strip():
            return

        selected_voice = voice or self.voice
        try:
            communicate = edge_tts.Communicate(text=text.strip(), voice=selected_voice)
            async for chunk in communicate.stream():
                if cancel_event and cancel_event.is_set():
                    logger.info("TTS stream interrupted by client.")
                    break

                if chunk["type"] == "audio" and "data" in chunk:
                    yield chunk["data"]
        except Exception as e:
            logger.warning("Edge TTS stream failed (%s). Providing fallback audio.", e)
            fallback = generate_silent_wav(duration_s=0.2)
            yield fallback

    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        """Synthesizes text into complete audio bytes (MP3)."""
        chunks = []
        async for chunk in self.stream_audio_chunks(text=text, voice=voice):
            chunks.append(chunk)
        return b"".join(chunks)


tts_service = EdgeTTSService()

