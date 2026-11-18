"""Voice Activity Detection (VAD) service.

Computes RMS energy of incoming audio streams, tracks silence/speech transitions,
and determines when an utterance is complete in continuous mode.
"""

import math
import struct
from typing import Tuple, Optional


class VoiceActivityDetector:
    """Detects active speech in PCM audio streams and tracks transitions."""

    def __init__(
        self,
        energy_threshold: float = 0.02,
        silence_timeout_seconds: float = 1.2,
        min_speech_duration_seconds: float = 0.3,
        sample_rate: int = 16000,
        sample_width_bytes: int = 2,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.silence_timeout_seconds = silence_timeout_seconds
        self.min_speech_duration_seconds = min_speech_duration_seconds
        self.sample_rate = sample_rate
        self.sample_width_bytes = sample_width_bytes

        # Internal state
        self.is_speech_active: bool = False
        self.speech_start_time: float = 0.0
        self.current_time: float = 0.0
        self.last_speech_time: float = 0.0
        self.speech_frames_count: int = 0
        self.silence_frames_count: int = 0

    def reset(self) -> None:
        """Reset internal state for a new audio session or utterance."""
        self.is_speech_active = False
        self.speech_start_time = 0.0
        self.current_time = 0.0
        self.last_speech_time = 0.0
        self.speech_frames_count = 0
        self.silence_frames_count = 0

    def calculate_rms(self, pcm_bytes: bytes) -> float:
        """Calculate Root Mean Square (RMS) energy normalized to [0.0, 1.0]."""
        if not pcm_bytes:
            return 0.0

        # Ensure full 16-bit samples
        num_samples = len(pcm_bytes) // self.sample_width_bytes
        if num_samples == 0:
            return 0.0

        format_str = f"<{num_samples}h"
        try:
            samples = struct.unpack(format_str, pcm_bytes[: num_samples * 2])
        except struct.error:
            return 0.0

        sum_squares = sum(s * s for s in samples)
        mean_square = sum_squares / num_samples
        rms = math.sqrt(mean_square)

        # Normalize relative to max signed 16-bit integer (32767)
        return min(1.0, rms / 32768.0)

    def process_chunk(self, pcm_bytes: bytes) -> Tuple[bool, Optional[str], float]:
        """Process an audio frame and return (is_voice, transition_event, rms_energy).

        Transition events:
        - "speech_start": Speech commenced
        - "speech_end": Silence threshold reached after active speech
        - None: Continuing previous state
        """
        rms = self.calculate_rms(pcm_bytes)
        num_samples = len(pcm_bytes) // self.sample_width_bytes
        frame_duration = num_samples / self.sample_rate if self.sample_rate > 0 else 0.0
        self.current_time += frame_duration

        is_voice = rms >= self.energy_threshold
        transition_event: Optional[str] = None

        if is_voice:
            self.speech_frames_count += 1
            self.silence_frames_count = 0
            self.last_speech_time = self.current_time

            if not self.is_speech_active:
                # Require at least 2 consecutive frames to avoid clicks
                if self.speech_frames_count >= 2:
                    self.is_speech_active = True
                    self.speech_start_time = self.current_time
                    transition_event = "speech_start"
        else:
            self.silence_frames_count += 1
            if self.is_speech_active:
                silence_elapsed = self.current_time - self.last_speech_time
                if silence_elapsed >= self.silence_timeout_seconds:
                    self.is_speech_active = False
                    transition_event = "speech_end"
                    self.speech_frames_count = 0

        return is_voice, transition_event, rms
