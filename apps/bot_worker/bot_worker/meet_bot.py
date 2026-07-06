"""Google Meet bot — Playwright-based browser automation.

Orchestrates the Google Meet–specific lifecycle: optional Google sign-in →
navigate to meeting → pre-join screen → wait for admission → monitor.
Inherits shared logic (browser launch, recording, cleanup) from BaseMeetingBot.
"""

from __future__ import annotations

import logging
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from bot_worker import selectors
from bot_worker.base_bot import BaseMeetingBot

logger = logging.getLogger(__name__)


class GoogleMeetBot(BaseMeetingBot):
    """Google Meet–specific bot implementation."""

    PLATFORM_NAME = "Google Meet"

    # =========================================================================
    # Platform-specific: navigate, pre-join, join, wait for admission
    # =========================================================================

    def _navigate_and_join(self) -> None:
        """Google Meet join flow: optional sign-in → navigate → pre-join → lobby."""
        assert self._page is not None

        if self._settings.use_google_login:
            self._google_sign_in()

        self._navigate_to_meet()
        self._handle_pre_join()
        self._wait_for_admission()

    # =========================================================================
    # Google Sign-In
    # =========================================================================

    def _google_sign_in(self) -> None:
        """Authenticate with Google before joining."""
        assert self._page is not None

        email = self._settings.google_email
        password = self._settings.google_password

        if not email or not password:
            raise ValueError("use_google_login is True but email/password not configured")

        self._log_event("GOOGLE_SIGN_IN_STARTED", {"email": email})
        logger.info("Starting Google sign-in for %s", email)

        try:
            # 1. Go to Google Login
            self._page.goto("https://accounts.google.com/", wait_until="networkidle", timeout=30000)

            # 2. Enter email
            self._human_typing(selectors.GOOGLE_EMAIL_INPUT, email)
            self._human_mouse_move(selectors.GOOGLE_EMAIL_NEXT)
            self._page.wait_for_selector(selectors.GOOGLE_EMAIL_NEXT, state="visible", timeout=5000).click()

            self._human_delay(1500, 3000)

            # 3. Enter password
            self._human_typing(selectors.GOOGLE_PASSWORD_INPUT, password)
            self._human_mouse_move(selectors.GOOGLE_PASSWORD_NEXT)
            self._page.wait_for_selector(selectors.GOOGLE_PASSWORD_NEXT, state="visible", timeout=5000).click()

            # 4. Wait for successful login
            self._page.wait_for_timeout(5000)
            self._page.wait_for_load_state("networkidle", timeout=30000)

            if "accounts.google.com/signin" in self._page.url or "accounts.google.com/v3/signin" in self._page.url:
                raise RuntimeError(f"Google login failed, stuck on {self._page.url}")

            self._log_event("GOOGLE_SIGN_IN_SUCCESS")
            logger.info("Google sign-in completed")

        except Exception as e:
            self._log_event("GOOGLE_SIGN_IN_FAILED", {"error": str(e)})
            logger.error("Google sign-in failed: %s", e)
            try:
                self._page.screenshot(path="login_error.png")
            except Exception:
                pass
            raise RuntimeError(f"Google sign-in failed: {e}")

    # =========================================================================
    # Navigation
    # =========================================================================

    def _navigate_to_meet(self) -> None:
        """Navigate to the Google Meet URL."""
        assert self._page is not None

        self._page.goto(self._meeting_url, wait_until="networkidle", timeout=30000)
        self._log_event("NAVIGATED", {"url": self._meeting_url})

        # Check for immediate errors
        self._check_for_errors()

        logger.info("Navigated to meeting: %s", self._meeting_url)

    # =========================================================================
    # Pre-join screen handling
    # =========================================================================

    def _handle_pre_join(self) -> None:
        """Handle the pre-join screen: dismiss dialogs, toggle mic/cam, click join."""
        assert self._page is not None

        self._page.wait_for_timeout(3000)  # Let the pre-join screen load

        # 1. Enter bot name if guest join
        if not self._settings.use_google_login:
            try:
                if self._page.is_visible(selectors.NAME_INPUT, timeout=2000):
                    self._human_typing(selectors.NAME_INPUT, self._settings.bot_display_name)
                    self._human_delay(300, 800)
            except Exception as e:
                logger.debug(f"Name input not found or failed: {e}")

        # 2. Dismiss any "Got it" dialogs
        try:
            if self._page.is_visible(selectors.DISMISS_BUTTON, timeout=1000):
                self._human_mouse_move(selectors.DISMISS_BUTTON)
                dismiss = self._page.query_selector(selectors.DISMISS_BUTTON)
                if dismiss:
                    dismiss.click()
                    self._human_delay(300, 800)
        except Exception:
            pass

        # 3. Turn off microphone
        try:
            if self._page.is_visible(selectors.MIC_TOGGLE, timeout=1000):
                self._human_mouse_move(selectors.MIC_TOGGLE)
                mic = self._page.query_selector(selectors.MIC_TOGGLE)
                if mic:
                    mic.click()
                    self._human_delay(300, 800)
        except Exception:
            pass

        # 4. Turn off camera
        try:
            if self._page.is_visible(selectors.CAMERA_TOGGLE, timeout=1000):
                self._human_mouse_move(selectors.CAMERA_TOGGLE)
                cam = self._page.query_selector(selectors.CAMERA_TOGGLE)
                if cam:
                    cam.click()
                    self._human_delay(300, 800)
        except Exception as e:
            logger.debug(f"Camera toggle not found or failed: {e}")

        # 5. Click "Ask to join" / "Join now"
        try:
            if self._page.is_visible(selectors.JOIN_BUTTON, timeout=2000):
                self._human_mouse_move(selectors.JOIN_BUTTON)
                join_btn = self._page.query_selector(selectors.JOIN_BUTTON)
                if join_btn:
                    join_btn.click()
            else:
                # Fallback selector
                self._human_mouse_move(selectors.JOIN_BUTTON_FALLBACK)
                join_btn = self._page.wait_for_selector(selectors.JOIN_BUTTON_FALLBACK, timeout=3000)
                if join_btn:
                    join_btn.click()
        except Exception as e:
            raise RuntimeError(f"Could not find the join button on pre-join screen: {e}")

        self._log_event("JOIN_CLICKED")
        self._update_status("WAITING_FOR_ADMISSION")
        logger.info("Join request sent, waiting for admission")

    # =========================================================================
    # Lobby / admission wait
    # =========================================================================

    def _wait_for_admission(self) -> None:
        """Wait for the host to admit the bot, with timeout."""
        assert self._page is not None

        timeout_ms = self._settings.lobby_timeout_seconds * 1000
        start_time = time.time()

        self._log_event("WAITING_IN_LOBBY")
        self._update_meeting_status("WAITING_FOR_ADMISSION")

        while True:
            elapsed = time.time() - start_time
            if elapsed * 1000 > timeout_ms:
                raise RuntimeError(
                    f"Lobby timeout after {self._settings.lobby_timeout_seconds}s — "
                    "host did not admit the bot"
                )

            # Check if we're in the meeting (admitted)
            try:
                self._page.wait_for_selector(
                    selectors.END_CALL_BUTTON, timeout=5000
                )
                logger.info("Admitted to meeting (detected end-call button)")
                return
            except PlaywrightTimeout:
                pass

            # Alternative: check for meeting toolbar
            try:
                if self._page.query_selector(selectors.END_CALL_BUTTON_ALT):
                    logger.info("Admitted to meeting (detected leave button)")
                    return
            except Exception:
                pass

            # Check for errors while waiting
            self._check_for_errors()

            # Brief pause before next check
            self._page.wait_for_timeout(2000)

    # =========================================================================
    # Meeting monitoring (Google Meet–specific end signals)
    # =========================================================================

    def _monitor_meeting(self) -> None:
        """Poll for Google Meet end signals.

        Checks every 5 seconds for:
        - "The meeting has ended" text
        - "You've been removed" text
        - End call button disappearing
        """
        assert self._page is not None

        logger.info("Monitoring meeting for end signals...")

        while True:
            try:
                # Check for meeting ended text
                if self._page.query_selector(selectors.MEETING_ENDED_TEXT):
                    logger.info("Detected: meeting has ended")
                    return

                # Check for removal
                if self._page.query_selector(selectors.REMOVED_TEXT):
                    logger.info("Detected: removed from meeting")
                    self._log_event("REMOVED_FROM_MEETING")
                    return

                # Check for left meeting
                if self._page.query_selector(selectors.LEFT_MEETING_TEXT):
                    logger.info("Detected: left the meeting")
                    return

                # Check for return/rejoin screen
                if self._page.query_selector(selectors.RETURN_HOME_BUTTON):
                    logger.info("Detected: return home screen")
                    return
                if self._page.query_selector(selectors.REJOIN_BUTTON):
                    logger.info("Detected: rejoin screen")
                    return

            except Exception:
                # Page might have navigated away — meeting ended
                logger.info("Page changed — assuming meeting ended")
                return

            self._page.wait_for_timeout(5000)

    # =========================================================================
    # Error detection (Google Meet–specific)
    # =========================================================================

    def _check_for_errors(self) -> None:
        """Check for Google Meet error states on the page."""
        assert self._page is not None

        error_selectors = [
            (selectors.MEETING_NOT_FOUND, "Meeting not found — invalid meeting link"),
            (selectors.MEETING_NOT_FOUND_ALT, "Meeting doesn't exist"),
            (selectors.CANNOT_JOIN, "Cannot join this meeting"),
            (selectors.CANNOT_JOIN_ALT, "Not allowed to join"),
        ]

        for selector, message in error_selectors:
            try:
                if self._page.query_selector(selector):
                    try:
                        self._page.screenshot(path="error_screenshot.png")
                    except Exception as e:
                        logger.error(f"Could not take screenshot: {e}")
                    raise RuntimeError(message)
            except RuntimeError:
                raise
            except Exception:
                pass  # Selector not found — good
