"""Whisper engine — local speech-to-text using faster-whisper.

Wraps the faster-whisper library for efficient local inference with
automatic language detection and VAD-based segmentation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from transcription_worker.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class Segment:
    """A single transcribed speech segment."""

    text: str
    start_ms: int
    end_ms: int
    language: str = "en"
    confidence: float | None = None
    speaker_label: str = "Unknown"


class WhisperEngine:
    """Local speech-to-text engine using faster-whisper.

    Lazily loads the Whisper model on first transcription call to avoid
    slow startup when importing the module.
    """

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ) -> None:
        self._model_size = model_size or settings.whisper_model_size
        self._device = device or settings.resolved_device
        self._compute_type = compute_type or settings.resolved_compute_type
        self._model = None

    def _ensure_model(self) -> None:
        """Lazily load the Whisper model."""
        if self._model is not None:
            return

        from faster_whisper import WhisperModel

        logger.info(
            "Loading Whisper model: %s (device=%s, compute_type=%s)",
            self._model_size,
            self._device,
            self._compute_type,
        )

        self._model = WhisperModel(
            self._model_size,
            device=self._device,
            compute_type=self._compute_type,
        )

        logger.info("Whisper model loaded successfully")

    def transcribe_chunk(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> list[Segment]:
        """Transcribe an audio file and return segments.

        Args:
            audio_path: Path to the audio file (WAV, WebM, FLAC, etc.).
            language: Optional language code. None = auto-detect.

        Returns:
            List of Segment objects with text, timestamps, and language.
        """
        self._ensure_model()
        assert self._model is not None

        segments_out: list[Segment] = []

        try:
            segments_iter, info = self._model.transcribe(
                str(audio_path),
                language=language,
                vad_filter=settings.vad_filter,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
                beam_size=5,
                best_of=5,
                word_timestamps=False,
            )

            detected_language = info.language
            logger.info(
                "Transcribing %s — detected language: %s (prob: %.2f)",
                audio_path.name,
                detected_language,
                info.language_probability,
            )

            for seg in segments_iter:
                segments_out.append(
                    Segment(
                        text=seg.text.strip(),
                        start_ms=int(seg.start * 1000),
                        end_ms=int(seg.end * 1000),
                        language=detected_language,
                        confidence=round(
                            sum(w.probability for w in (seg.words or []))
                            / max(len(seg.words or []), 1),
                            4,
                        ) if seg.words else None,
                    )
                )

        except Exception:
            logger.exception("Transcription failed for %s", audio_path)
            raise

        logger.info(
            "Transcribed %s → %d segments",
            audio_path.name,
            len(segments_out),
        )
        return segments_out

    def detect_language(self, audio_path: Path) -> str:
        """Detect the primary language of an audio file.

        Returns:
            ISO language code (e.g., 'en', 'hi').
        """
        self._ensure_model()
        assert self._model is not None

        _, info = self._model.transcribe(
            str(audio_path),
            language=None,
            vad_filter=True,
        )
        return info.language
