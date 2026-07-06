"""Abstract base class for meeting bots.

Shared lifecycle logic for all meeting platforms (Google Meet, Jitsi, etc.):
browser launch → join → record → monitor → cleanup.
"""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from pathlib import Path

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
    TimeoutError as PlaywrightTimeout,
)

from bot_worker.api_client import BotAPIClient
from bot_worker.audio_capture import AudioCaptureManager
from bot_worker.config import BotWorkerSettings, get_settings
from bot_worker.minio_client import MinIOUploader

logger = logging.getLogger(__name__)


class BaseMeetingBot(ABC):
    """Abstract base for platform-specific meeting bots.

    Subclasses must implement:
    - ``_navigate_and_join()`` — platform-specific navigation, pre-join, and join
    - ``_monitor_meeting()`` — poll for platform-specific meeting-end signals
    - ``_check_for_errors()`` — detect platform-specific error pages
    """

    # Human-readable platform name for logging
    PLATFORM_NAME: str = "Unknown"

    def __init__(
        self,
        meeting_url: str,
        meeting_id: str,
        session_id: str,
        api_client: BotAPIClient,
        settings: BotWorkerSettings | None = None,
    ) -> None:
        self._meeting_url = meeting_url
        self._meeting_id = meeting_id
        self._session_id = session_id
        self._api = api_client
        self._settings = settings or get_settings()

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

        self._audio_capture = AudioCaptureManager()
        self._minio = MinIOUploader()

        # Wire up audio chunk callback → MinIO upload → API registration
        self._audio_capture.set_chunk_callback(self._on_audio_chunk)

    # =========================================================================
    # Human-simulation helpers (shared across all platforms)
    # =========================================================================

    def _human_delay(self, min_ms: int = 500, max_ms: int = 2000) -> None:
        """Add a randomized sleep delay to mimic human reaction time."""
        if self._page:
            delay = random.uniform(min_ms, max_ms)
            self._page.wait_for_timeout(delay)

    def _human_mouse_move(self, selector: str) -> None:
        """Move the mouse to an element realistically using a Bezier curve."""
        if not self._page:
            return
        try:
            element = self._page.wait_for_selector(selector, timeout=5000)
            if element:
                box = element.bounding_box()
                if box:
                    # Target point inside the element
                    target_x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
                    target_y = box["y"] + box["height"] * random.uniform(0.2, 0.8)

                    # Random starting position nearby
                    start_x = target_x + random.uniform(-200, 200)
                    start_y = target_y + random.uniform(-200, 200)

                    self._page.mouse.move(start_x, start_y)

                    # Bezier curve movement
                    steps = random.randint(15, 30)
                    ctrl_x = (start_x + target_x) / 2 + random.uniform(-100, 100)
                    ctrl_y = (start_y + target_y) / 2 + random.uniform(-100, 100)

                    for i in range(1, steps + 1):
                        t = i / steps
                        # Easing out (slower at the end)
                        t = 1 - (1 - t) * (1 - t)

                        # Quadratic bezier
                        current_x = (1 - t)**2 * start_x + 2 * (1 - t) * t * ctrl_x + t**2 * target_x
                        current_y = (1 - t)**2 * start_y + 2 * (1 - t) * t * ctrl_y + t**2 * target_y

                        self._page.mouse.move(current_x, current_y)
                        self._page.wait_for_timeout(random.randint(10, 30))

                    self._human_delay(100, 400)
        except Exception as e:
            logger.debug(f"Human mouse move failed for {selector}: {e}")

    def _human_typing(self, selector: str, text: str) -> None:
        """Type text character by character with random delays and occasional pauses."""
        if not self._page:
            return

        self._human_mouse_move(selector)
        element = self._page.wait_for_selector(selector, state="visible", timeout=10000)
        if element:
            element.click()
            self._human_delay(100, 300)
            for char in text:
                element.type(char)
                delay_ms = random.randint(40, 150)
                # 5% chance to pause (simulating thinking/reading/finding a key)
                if random.random() < 0.05:
                    delay_ms += random.randint(200, 600)
                self._page.wait_for_timeout(delay_ms)

    # =========================================================================
    # Lifecycle orchestration
    # =========================================================================

    def run(self) -> None:
        """Main entry point — orchestrates the full bot lifecycle.

        Status transitions: JOINING → WAITING_FOR_ADMISSION → JOINED → RECORDING → ENDED/FAILED
        """
        try:
            self._update_status("JOINING")
            self._log_event("BROWSER_LAUNCHED", {
                "headless": self._settings.headless,
                "platform": self.PLATFORM_NAME,
            })

            self._launch_browser()
            self._navigate_and_join()

            # Successfully joined
            self._update_status("JOINED")
            self._update_meeting_status("IN_PROGRESS")
            self._log_event("ADMITTED")

            # Start audio capture
            self._start_recording()

            # Monitor until meeting ends
            self._monitor_meeting()

            # Clean exit
            self._stop_recording()
            self._update_status("ENDED")
            self._log_event("MEETING_ENDED", {
                "chunks_recorded": self._audio_capture.chunk_count,
            })

            # Transition meeting to transcription
            self._update_meeting_status("PROCESSING_TRANSCRIPT")

        except Exception as e:
            logger.exception("Bot failed: %s", e)
            self._stop_recording()
            self._update_status("FAILED", failure_reason=str(e))
            self._update_meeting_status("FAILED")
            self._log_event("ERROR", {"error": str(e)})
            raise
        finally:
            self._cleanup()

    # =========================================================================
    # Browser launch (shared)
    # =========================================================================

    def _launch_browser(self) -> None:
        """Launch Chromium with audio capture flags and stealth features."""
        self._playwright = sync_playwright().start()

        args = [
            "--disable-blink-features=AutomationControlled",
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-infobars",
            "--disable-extensions",
            "--window-position=0,0",
            "--ignore-certificate-errors",
            "--no-sandbox",
        ]

        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )

        self._browser = self._playwright.chromium.launch(
            channel="msedge",
            headless=self._settings.headless,
            args=args,
        )

        # Use realistic standard viewports
        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1536, "height": 864},
            {"width": 1280, "height": 720},
        ]
        viewport = random.choice(viewports)
        width, height = viewport["width"], viewport["height"]

        self._context = self._browser.new_context(
            user_agent=user_agent,
            permissions=["microphone", "camera"],
            viewport={"width": width, "height": height},
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"longitude": -74.006, "latitude": 40.7128},
            color_scheme="dark",
        )
        self._page = self._context.new_page()

        # Comprehensive stealth script to bypass detection
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """
        self._page.add_init_script(stealth_js)

        logger.info(
            "Browser launched (headless=%s, viewport=%dx%d, platform=%s)",
            self._settings.headless, width, height, self.PLATFORM_NAME,
        )

    # =========================================================================
    # Abstract methods — each platform must implement
    # =========================================================================

    @abstractmethod
    def _navigate_and_join(self) -> None:
        """Platform-specific: navigate to meeting, handle pre-join, click join, wait for admission."""
        ...

    @abstractmethod
    def _monitor_meeting(self) -> None:
        """Platform-specific: poll for meeting-end signals and return when the meeting is over."""
        ...

    @abstractmethod
    def _check_for_errors(self) -> None:
        """Platform-specific: check the current page for error states and raise RuntimeError."""
        ...

    # =========================================================================
    # Recording (shared)
    # =========================================================================

    def _start_recording(self) -> None:
        """Start audio capture and transition to RECORDING status."""
        assert self._page is not None

        self._audio_capture.start_capture(
            self._page, self._meeting_id, self._session_id
        )
        self._update_status("RECORDING")
        self._log_event("RECORDING_STARTED")
        logger.info("Audio recording started")

    def _stop_recording(self) -> None:
        """Stop audio capture if active."""
        if self._page and self._audio_capture.is_capturing:
            total = self._audio_capture.stop_capture(self._page)
            self._log_event("RECORDING_STOPPED", {"total_chunks": total})
            logger.info("Audio recording stopped (%d chunks)", total)

    def _on_audio_chunk(self, chunk_path: Path, chunk_index: int) -> None:
        """Callback: upload chunk to MinIO and register via API."""
        try:
            # Upload to MinIO
            minio_key = self._minio.upload_chunk(
                local_path=chunk_path,
                meeting_id=self._meeting_id,
                session_id=self._session_id,
                chunk_index=chunk_index,
            )

            # Register with API
            size_bytes = chunk_path.stat().st_size
            duration_ms = self._settings.audio_chunk_duration_seconds * 1000

            self._api.register_audio_chunk(
                session_id=self._session_id,
                chunk_index=chunk_index,
                minio_key=minio_key,
                duration_ms=duration_ms,
                size_bytes=size_bytes,
            )

            self._log_event("CHUNK_UPLOADED", {
                "chunk_index": chunk_index,
                "minio_key": minio_key,
                "size_bytes": size_bytes,
            })

        except Exception:
            logger.exception("Failed to upload/register chunk %d", chunk_index)

    # =========================================================================
    # API helpers (shared)
    # =========================================================================

    def _update_status(
        self, status: str, failure_reason: str | None = None
    ) -> None:
        """Update bot session status via API."""
        try:
            self._api.update_session_status(
                self._session_id, status, failure_reason
            )
        except Exception:
            logger.exception("Failed to update status to %s", status)

    def _update_meeting_status(self, status: str) -> None:
        """Update the meeting's status via API (e.g. IN_PROGRESS, PROCESSING_TRANSCRIPT)."""
        try:
            self._api.update_meeting_status(self._meeting_id, status)
            logger.info("Updated meeting status to %s", status)
        except Exception as e:
            logger.error("Failed to update meeting status to %s: %s", status, e)

    def _log_event(
        self, event_type: str, details: dict | None = None
    ) -> None:
        """Log an event to the bot session via API."""
        try:
            self._api.log_event(self._session_id, event_type, details)
        except Exception:
            logger.exception("Failed to log event %s", event_type)

    # =========================================================================
    # Cleanup (shared)
    # =========================================================================

    def _cleanup(self) -> None:
        """Close browser and clean up resources."""
        self._log_event("CLEANUP")

        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            logger.exception("Error during browser cleanup")

        # Clean up temporary recording files
        self._audio_capture.cleanup()
        logger.info("Bot cleanup completed")
