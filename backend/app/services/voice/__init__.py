"""Voice AI package: VAD, Whisper STT, Edge-TTS, and Voice Session Management."""

import sys

# Compatibility patch for PyAV 14+ with faster-whisper (removes obsolete metadata_errors parameter)
try:
    import av
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except (ImportError, AttributeError):
    pass

from app.services.voice.vad import VoiceActivityDetector
from app.services.voice.stt import WhisperSTTService, whisper_service
from app.services.voice.tts import EdgeTTSService, tts_service
from app.services.voice.session import VoiceSession, VoiceSessionManager, voice_session_manager

__all__ = [
    "VoiceActivityDetector",
    "WhisperSTTService",
    "whisper_service",
    "EdgeTTSService",
    "tts_service",
    "VoiceSession",
    "VoiceSessionManager",
    "voice_session_manager",
]

