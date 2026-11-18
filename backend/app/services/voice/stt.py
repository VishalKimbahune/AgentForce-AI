"""Speech-to-Text (STT) service using faster-whisper."""

import asyncio
import io
import logging
import os
import struct
import tempfile
import wave
from typing import Any, Dict, List, Optional, Union

# Compatibility patch for PyAV 14+ with faster-whisper
try:
    import av

    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except (ImportError, AttributeError):
    pass

from faster_whisper import WhisperModel
from app.core.config import settings

logger = logging.getLogger("voice.stt")


def pcm_to_wav_bytes(
    pcm_bytes: bytes,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wraps raw PCM audio bytes with a standard WAV container header."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


class WhisperSTTService:
    """Wrapper around faster-whisper for asynchronous speech transcription."""

    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or getattr(settings, "WHISPER_MODEL", "tiny")
        self._model: Optional[WhisperModel] = None
        self._lock = asyncio.Lock()

    def _get_model(self) -> WhisperModel:
        """Lazily instantiates the faster-whisper model on CPU."""
        if self._model is None:
            # Try specified model; fallback to 'tiny' if requested model fails to load
            target_model = self.model_size
            try:
                logger.info("Loading Whisper model '%s' on CPU (int8)...", target_model)
                self._model = WhisperModel(target_model, device="cpu", compute_type="int8")
            except Exception as e:
                logger.warning("Failed loading '%s': %s. Falling back to 'tiny'.", target_model, e)
                self._model = WhisperModel("tiny", device="cpu", compute_type="int8")
        return self._model

    def transcribe_sync(
        self,
        audio_source: Union[str, bytes, io.BytesIO],
        language: Optional[str] = "en",
        beam_size: int = 1,
    ) -> Dict[str, Any]:
        """Synchronously transcribes audio to text."""
        model = self._get_model()

        temp_path: Optional[str] = None
        try:
            if isinstance(audio_source, bytes):
                # Check for standard container signatures
                is_container = (
                    audio_source.startswith(b"RIFF")
                    or audio_source.startswith(b"\x1aE\xdf\xa3")  # WebM
                    or audio_source.startswith(b"ID3")  # MP3 ID3
                    or audio_source.startswith(b"\xff\xfb")  # MP3 frame
                    or audio_source.startswith(b"OggS")  # OGG
                )
                if not is_container:
                    # Convert raw PCM to WAV
                    audio_bytes = pcm_to_wav_bytes(audio_source)
                else:
                    audio_bytes = audio_source

                suffix = ".webm" if audio_source.startswith(b"\x1aE\xdf\xa3") else ".wav"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                    tf.write(audio_bytes)
                    temp_path = tf.name
                input_file = temp_path

            elif isinstance(audio_source, io.BytesIO):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    tf.write(audio_source.getvalue())
                    temp_path = tf.name
                input_file = temp_path

            else:
                input_file = audio_source

            if not os.path.exists(input_file) or os.path.getsize(input_file) == 0:
                return {
                    "text": "",
                    "language": language or "en",
                    "duration": 0.0,
                    "segments": [],
                }

            segments, info = model.transcribe(
                input_file,
                language=language,
                beam_size=beam_size,
                vad_filter=True,
            )

            segment_list = []
            full_texts = []
            for s in segments:
                text_clean = s.text.strip()
                if text_clean:
                    full_texts.append(text_clean)
                    segment_list.append(
                        {
                            "id": s.id,
                            "start": round(s.start, 2),
                            "end": round(s.end, 2),
                            "text": text_clean,
                        }
                    )

            transcript = " ".join(full_texts).strip()
            return {
                "text": transcript,
                "language": info.language,
                "language_probability": round(info.language_probability, 3),
                "duration": round(info.duration, 2),
                "segments": segment_list,
            }

        except Exception as e:
            logger.error("Error during Whisper transcription: %s", str(e), exc_info=True)
            return {
                "text": "",
                "error": str(e),
                "language": language or "en",
                "duration": 0.0,
                "segments": [],
            }
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    async def transcribe(
        self,
        audio_source: Union[str, bytes, io.BytesIO],
        language: Optional[str] = "en",
        beam_size: int = 1,
    ) -> Dict[str, Any]:
        """Asynchronously transcribes audio without blocking the event loop."""
        return await asyncio.to_thread(
            self.transcribe_sync,
            audio_source,
            language=language,
            beam_size=beam_size,
        )


whisper_service = WhisperSTTService()

