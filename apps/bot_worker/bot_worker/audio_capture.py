"""Audio capture manager — captures browser tab audio via JavaScript MediaRecorder.

Uses Playwright's page.evaluate() to inject a MediaRecorder that captures
audio from the tab, producing WebM/Opus chunks at configurable intervals.
Chunks are saved to disk for upload to MinIO.
"""

from __future__ import annotations

import base64
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from playwright.sync_api import Page

from bot_worker.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AudioCaptureManager:
    """Manages browser audio capture via injected JavaScript MediaRecorder.

    The capture flow:
    1. Inject JS that creates an AudioContext capturing tab audio
    2. MediaRecorder records in chunks (default 30s)
    3. Each chunk is base64-encoded and sent back to Python via page.expose_function
    4. Python saves chunks to disk for MinIO upload
    """

    def __init__(
        self,
        recording_dir: str | None = None,
        chunk_duration_seconds: int | None = None,
    ) -> None:
        self._chunk_duration_ms = (
            chunk_duration_seconds or settings.audio_chunk_duration_seconds
        ) * 1000
        self._recording_dir = Path(
            recording_dir or settings.recording_dir
        )
        self._recording_dir.mkdir(parents=True, exist_ok=True)
        self._chunk_index = 0
        self._session_dir: Path | None = None
        self._is_capturing = False
        self._chunk_callback: Callable[[Path, int], None] | None = None

    def set_chunk_callback(
        self, callback: Callable[[Path, int], None]
    ) -> None:
        """Set a callback that's called for each chunk: callback(chunk_path, chunk_index)."""
        self._chunk_callback = callback

    def start_capture(
        self,
        page: Page,
        meeting_id: str,
        session_id: str,
    ) -> None:
        """Start capturing audio from the browser tab.

        Args:
            page: The Playwright page with the active Google Meet session.
            meeting_id: Meeting UUID for organizing recordings.
            session_id: Bot session UUID.
        """
        self._session_dir = self._recording_dir / meeting_id / session_id
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._chunk_index = 0

        # Expose a Python function that JS will call with each audio chunk
        page.expose_function(
            "_onAudioChunk",
            lambda data: self._handle_chunk(data),
        )

        # Inject the MediaRecorder JavaScript
        chunk_duration_ms = self._chunk_duration_ms
        page.evaluate(f"""() => {{
            const audioCtx = new AudioContext();
            const destination = audioCtx.createMediaStreamDestination();
            
            // Store globally for the interceptor
            window._audioCtx = audioCtx;
            window._audioDestination = destination;

            // 1. Intercept srcObject assignment on all media elements
            // This guarantees we catch WebRTC streams exactly when Jitsi/Meet assigns them,
            // avoiding MutationObserver timing issues where srcObject is null when added to DOM.
            const originalSrcObject = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'srcObject');
            if (originalSrcObject) {{
                Object.defineProperty(HTMLMediaElement.prototype, 'srcObject', {{
                    set: function(stream) {{
                        if (stream) {{
                            try {{
                                const source = window._audioCtx.createMediaStreamSource(stream);
                                source.connect(window._audioDestination);
                            }} catch(e) {{
                                console.log('Failed to capture srcObject stream:', e.message);
                            }}
                        }}
                        return originalSrcObject.set.call(this, stream);
                    }},
                    get: function() {{
                        return originalSrcObject.get.call(this);
                    }}
                }});
            }}

            // 2. Also capture any existing elements (fallback)
            const mediaElements = document.querySelectorAll('audio, video');
            mediaElements.forEach(el => {{
                try {{
                    if (el.srcObject) {{
                        const source = audioCtx.createMediaStreamSource(el.srcObject);
                        source.connect(destination);
                    }} else if (el.captureStream) {{
                        const source = audioCtx.createMediaStreamSource(el.captureStream());
                        source.connect(destination);
                    }} else {{
                        const source = audioCtx.createMediaElementSource(el);
                        source.connect(destination);
                    }}
                }} catch (e) {{
                    console.log('Audio element capture failed:', e.message);
                }}
            }});

            // 3. Create MediaRecorder
            const recorder = new MediaRecorder(destination.stream, {{
                mimeType: 'audio/webm;codecs=opus',
            }});

            recorder.ondataavailable = async (event) => {{
                if (event.data.size > 0) {{
                    const reader = new FileReader();
                    reader.onloadend = () => {{
                        const base64data = reader.result.split(',')[1];
                        window._onAudioChunk(base64data);
                    }};
                    reader.readAsDataURL(event.data);
                }}
            }};

            recorder.start({chunk_duration_ms});
            window._audioRecorder = recorder;
        }}""")

        self._is_capturing = True
        logger.info(
            "Audio capture started (chunk interval: %dms)",
            self._chunk_duration_ms,
        )

    def _handle_chunk(self, base64_data: str) -> None:
        """Handle a base64-encoded audio chunk from the browser."""
        if self._session_dir is None:
            logger.warning("Received chunk but no session directory set")
            return

        chunk_path = self._session_dir / f"chunk_{self._chunk_index:04d}.webm"

        # Decode and save
        audio_bytes = base64.b64decode(base64_data)
        chunk_path.write_bytes(audio_bytes)

        logger.info(
            "Saved audio chunk %d (%d bytes) → %s",
            self._chunk_index,
            len(audio_bytes),
            chunk_path,
        )

        # Call the upload callback if set
        if self._chunk_callback:
            try:
                self._chunk_callback(chunk_path, self._chunk_index)
            except Exception:
                logger.exception(
                    "Chunk callback failed for chunk %d", self._chunk_index
                )

        self._chunk_index += 1

    def stop_capture(self, page: Page) -> int:
        """Stop audio capture and return the total number of chunks recorded.

        Args:
            page: The Playwright page.

        Returns:
            Total number of chunks recorded.
        """
        if not self._is_capturing:
            return self._chunk_index

        try:
            page.evaluate("""() => {
                if (window._audioRecorder && window._audioRecorder.state !== 'inactive') {
                    window._audioRecorder.stop();
                }
                if (window._audioCtx) {
                    window._audioCtx.close();
                }
            }""")
        except Exception:
            logger.exception("Error stopping audio capture JS")

        self._is_capturing = False
        total = self._chunk_index
        logger.info("Audio capture stopped. Total chunks: %d", total)
        return total

    def cleanup(self) -> None:
        """Remove temporary recording files."""
        if self._session_dir and self._session_dir.exists():
            shutil.rmtree(self._session_dir, ignore_errors=True)
            logger.info("Cleaned up recording directory: %s", self._session_dir)
            
            # Also clean up the parent meeting_id directory if it's empty
            parent_dir = self._session_dir.parent
            if parent_dir.exists() and parent_dir != self._recording_dir:
                try:
                    # rmdir only succeeds if the directory is empty
                    parent_dir.rmdir()
                except OSError:
                    pass

    @property
    def chunk_count(self) -> int:
        """Current number of chunks recorded."""
        return self._chunk_index

    @property
    def is_capturing(self) -> bool:
        """Whether capture is currently active."""
        return self._is_capturing
