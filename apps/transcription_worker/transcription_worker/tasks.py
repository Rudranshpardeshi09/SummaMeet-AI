"""Celery tasks for the transcription worker.

Defines the `transcribe_meeting` task that processes audio chunks through
faster-whisper and persists transcript segments to the API.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from celery import Task

from transcription_worker.api_client import TranscriptionAPIClient
from transcription_worker.celery_app import celery_app
from transcription_worker.config import get_settings
from transcription_worker.diarizer import SpeakerDiarizer
from transcription_worker.minio_client import MinIODownloader
from transcription_worker.whisper_engine import WhisperEngine

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazily initialized shared instances (heavy objects, load once per worker)
_whisper_engine: WhisperEngine | None = None
_diarizer: SpeakerDiarizer | None = None


def _get_whisper_engine() -> WhisperEngine:
    """Get or create the singleton Whisper engine."""
    global _whisper_engine
    if _whisper_engine is None:
        _whisper_engine = WhisperEngine()
    return _whisper_engine


def _get_diarizer() -> SpeakerDiarizer:
    """Get or create the singleton speaker diarizer."""
    global _diarizer
    if _diarizer is None:
        _diarizer = SpeakerDiarizer()
    return _diarizer


@celery_app.task(
    bind=True,
    name="transcription_worker.tasks.transcribe_meeting",
    max_retries=2,
    acks_late=True,
    reject_on_worker_lost=True,
    default_retry_delay=60,
)
def transcribe_meeting(
    self: Task,
    meeting_id: str,
    session_id: str,
) -> dict:
    """Transcribe all audio chunks for a meeting session.

    Flow:
    1. Fetch audio chunk list from API
    2. Download each chunk from MinIO
    3. Run through Whisper for transcription
    4. Assign speaker labels via diarizer
    5. Batch persist segments to API
    6. Update meeting status to GENERATING_REPORT

    Args:
        meeting_id: UUID of the meeting.
        session_id: UUID of the bot session whose audio to transcribe.

    Returns:
        Dict with meeting_id, total segments, and status.
    """
    logger.info(
        "Starting transcription for meeting %s (session %s, attempt %d/%d)",
        meeting_id,
        session_id,
        (self.request.retries or 0) + 1,
        (self.max_retries or 0) + 1,
    )

    download_dir = Path(settings.download_dir) / meeting_id / session_id
    download_dir.mkdir(parents=True, exist_ok=True)

    whisper = _get_whisper_engine()
    diarizer = _get_diarizer()
    minio = MinIODownloader()

    with TranscriptionAPIClient() as api_client:
        try:
            # 1. Fetch ordered audio chunks
            chunks = api_client.get_audio_chunks(session_id)

            if not chunks:
                logger.warning(
                    "No audio chunks found for session %s", session_id
                )
                api_client.update_meeting_status(meeting_id, "FAILED")
                return {
                    "meeting_id": meeting_id,
                    "status": "FAILED",
                    "error": "No audio chunks found",
                }

            logger.info("Found %d audio chunks to process", len(chunks))

            # 2. Download and concatenate all chunks
            merged_path = download_dir / "merged.webm"
            with open(merged_path, "wb") as outfile:
                for chunk_info in chunks:
                    minio_key = chunk_info["minio_key"]
                    logger.info("Downloading chunk %d: %s", chunk_info["chunk_index"], minio_key)
                    
                    local_path = minio.download_chunk(minio_key, download_dir)
                    
                    # Append chunk to merged file
                    with open(local_path, "rb") as infile:
                        shutil.copyfileobj(infile, outfile)
                        
                    # Clean up downloaded individual chunk
                    try:
                        local_path.unlink()
                    except Exception:
                        pass

            # 3. Transcribe the merged file
            logger.info("Transcribing merged audio file: %s", merged_path)
            all_segments = []
            try:
                all_segments = whisper.transcribe_chunk(merged_path)
            except Exception as e:
                logger.exception("Failed to transcribe merged audio")
                # We raise here because if the entire meeting fails to transcribe, it should retry or fail permanently.
                raise e

            if not all_segments:
                logger.warning("No segments produced from transcription")
                import httpx
                try:
                    api_client.update_meeting_status(meeting_id, "GENERATING_REPORT")
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 409:
                        logger.warning("Meeting status transition rejected (409 Conflict), likely already processed.")
                    else:
                        raise
                return {
                    "meeting_id": meeting_id,
                    "status": "COMPLETED_EMPTY",
                    "error": None,
                }

            # 4. Speaker diarization
            all_segments = diarizer.assign_speakers(all_segments)

            # 5. Batch persist to API
            batch_size = settings.batch_size
            total_persisted = 0
            global_sequence = 0

            for i in range(0, len(all_segments), batch_size):
                batch = all_segments[i : i + batch_size]

                segment_dicts = []
                for seg in batch:
                    segment_dicts.append({
                        "sequence_no": global_sequence,
                        "speaker_label": seg.speaker_label,
                        "language": seg.language,
                        "start_ms": seg.start_ms,
                        "end_ms": seg.end_ms,
                        "text": seg.text,
                        "confidence": seg.confidence,
                    })
                    global_sequence += 1

                api_client.create_transcript_segments_batch(
                    meeting_id=meeting_id,
                    bot_session_id=session_id,
                    segments=segment_dicts,
                )
                total_persisted += len(batch)

                logger.info(
                    "Persisted %d/%d segments",
                    total_persisted,
                    len(all_segments),
                )

            # 6. Transition meeting to next phase
            try:
                api_client.update_meeting_status(
                    meeting_id, "GENERATING_REPORT"
                )
            except Exception:
                logger.exception(
                    "Failed to transition meeting to GENERATING_REPORT"
                )

            logger.info(
                "Transcription complete: %d segments from %d chunks",
                len(all_segments),
                len(chunks),
            )

            return {
                "meeting_id": meeting_id,
                "session_id": session_id,
                "status": "COMPLETED",
                "total_segments": len(all_segments),
                "total_chunks": len(chunks),
            }

        except Exception as exc:
            retries_left = (self.max_retries or 0) - (self.request.retries or 0)

            if retries_left > 0:
                countdown = 60 * (2 ** (self.request.retries or 0))
                logger.warning(
                    "Transcription failed, retrying in %ds: %s",
                    countdown,
                    str(exc),
                )
                raise self.retry(exc=exc, countdown=countdown)
            else:
                logger.error(
                    "Transcription failed permanently: %s", str(exc)
                )
                try:
                    api_client.update_meeting_status(meeting_id, "FAILED")
                except Exception:
                    logger.exception("Failed to mark meeting as FAILED")

                return {
                    "meeting_id": meeting_id,
                    "status": "FAILED",
                    "error": str(exc),
                }

        finally:
            # Clean up download directory
            try:
                if download_dir.exists():
                    shutil.rmtree(download_dir, ignore_errors=True)
            except Exception:
                pass
