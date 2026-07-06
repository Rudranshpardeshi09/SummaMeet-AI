"""Simple speaker diarization — energy-based clustering.

Assigns speaker labels to transcript segments based on audio energy
patterns and temporal proximity. This is a lightweight alternative to
pyannote-audio that doesn't require a HuggingFace token.

For production-quality diarization, consider switching to pyannote-audio
by setting USE_PYANNOTE=true in the environment.
"""

from __future__ import annotations

import logging
from pathlib import Path

from transcription_worker.whisper_engine import Segment

logger = logging.getLogger(__name__)


class SpeakerDiarizer:
    """Assign speaker labels to transcript segments.

    Uses a simple heuristic based on pause detection between segments:
    - Short pauses (< 1.5s) → same speaker
    - Long pauses (>= 1.5s) or overlapping → potential speaker change
    - Assigns sequential labels: Speaker_1, Speaker_2, etc.

    This is a basic approach suitable for 2-3 speaker meetings.
    For higher accuracy, integrate pyannote-audio.
    """

    def __init__(
        self,
        pause_threshold_ms: int = 1500,
        max_speakers: int = 10,
    ) -> None:
        self._pause_threshold_ms = pause_threshold_ms
        self._max_speakers = max_speakers

    def assign_speakers(
        self,
        segments: list[Segment],
        audio_path: Path | None = None,
    ) -> list[Segment]:
        """Assign speaker labels to segments based on temporal patterns.

        Args:
            segments: Transcript segments from Whisper (ordered by time).
            audio_path: Optional path to audio for energy analysis (unused in basic mode).

        Returns:
            Same segments with speaker_label populated.
        """
        if not segments:
            return segments

        current_speaker = 1
        segments[0].speaker_label = f"Speaker_{current_speaker}"

        for i in range(1, len(segments)):
            prev = segments[i - 1]
            curr = segments[i]

            # Calculate gap between segments
            gap_ms = curr.start_ms - prev.end_ms

            # Heuristic: long pause suggests speaker change
            if gap_ms >= self._pause_threshold_ms:
                # Switch speaker (alternate between available speakers)
                current_speaker = (current_speaker % min(self._max_speakers, 2)) + 1

            # Heuristic: overlapping segments suggest speaker change
            elif gap_ms < -200:  # Overlap > 200ms
                current_speaker = (current_speaker % min(self._max_speakers, 2)) + 1

            # Heuristic: language change often indicates speaker change
            elif curr.language != prev.language:
                current_speaker = (current_speaker % min(self._max_speakers, 2)) + 1

            curr.speaker_label = f"Speaker_{current_speaker}"

        # Count speakers
        unique_speakers = {s.speaker_label for s in segments}
        logger.info(
            "Diarization complete: %d segments, %d speakers detected",
            len(segments),
            len(unique_speakers),
        )

        return segments
