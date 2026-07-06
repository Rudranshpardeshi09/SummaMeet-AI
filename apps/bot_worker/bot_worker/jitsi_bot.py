"""Jitsi Meet bot — Playwright-based browser automation.

Handles the Jitsi-specific lifecycle: navigate to meeting URL →
enter display name → join → monitor for end signals.
Inherits shared logic (browser launch, recording, cleanup) from BaseMeetingBot.
"""

from __future__ import annotations

import logging

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from bot_worker import jitsi_selectors as selectors
from bot_worker.base_bot import BaseMeetingBot

logger = logging.getLogger(__name__)


class JitsiMeetBot(BaseMeetingBot):
    """Jitsi Meet–specific bot implementation."""

    PLATFORM_NAME = "Jitsi Meet"

    # =========================================================================
    # Platform-specific: navigate, pre-join, join
    # =========================================================================

    def _navigate_and_join(self) -> None:
        """Jitsi join flow: navigate → enter name → click join → confirm in meeting."""
        assert self._page is not None

        # 1. Navigate to the Jitsi meeting URL
        self._page.goto(self._meeting_url, wait_until="networkidle", timeout=30000)
        self._log_event("NAVIGATED", {"url": self._meeting_url})
        logger.info("Navigated to Jitsi meeting: %s", self._meeting_url)

        # Check for immediate errors
        self._check_for_errors()

        # 2. Wait for the pre-join screen to load
        self._page.wait_for_timeout(3000)

        # 3. Enter the bot display name
        try:
            name_input = self._page.wait_for_selector(selectors.NAME_INPUT, state="visible", timeout=5000)
            if name_input:
                name_input.click()
                self._page.keyboard.press("Control+a")
                self._page.keyboard.press("Backspace")
                self._human_typing(
                    selectors.NAME_INPUT, self._settings.bot_display_name
                )
                logger.info(f"Entered display name: {self._settings.bot_display_name}")
        except Exception as e:
            logger.debug(f"Could not enter name (maybe not requested): {e}")

        # 4. Turn off microphone and camera (if active)
        # Jitsi's aria-labels change based on state. If it says "Mute microphone", it is currently unmuted.
        try:
            mic_btn = self._page.wait_for_selector(selectors.MIC_TOGGLE, state="visible", timeout=3000)
            if mic_btn:
                self._human_mouse_move(selectors.MIC_TOGGLE)
                mic_btn.click()
                self._human_delay(300, 800)
                logger.info("Muted Jitsi microphone")
        except Exception as e:
            logger.debug(f"Could not mute microphone: {e}")

        try:
            cam_btn = self._page.wait_for_selector(selectors.CAMERA_TOGGLE, state="visible", timeout=3000)
            if cam_btn:
                self._human_mouse_move(selectors.CAMERA_TOGGLE)
                cam_btn.click()
                self._human_delay(300, 800)
                logger.info("Stopped Jitsi camera")
        except Exception as e:
            logger.debug(f"Could not stop camera: {e}")

        # 5. Click "Join meeting"
        joined = False
        try:
            join_btn = self._page.wait_for_selector(selectors.JOIN_BUTTON, state="visible", timeout=3000)
            if join_btn:
                self._human_mouse_move(selectors.JOIN_BUTTON)
                join_btn.click()
                joined = True
        except Exception:
            pass

        if not joined:
            try:
                self._human_mouse_move(selectors.JOIN_BUTTON_FALLBACK)
                join_btn = self._page.wait_for_selector(
                    selectors.JOIN_BUTTON_FALLBACK, timeout=5000
                )
                if join_btn:
                    join_btn.click()
                    joined = True
            except PlaywrightTimeout:
                pass

        if not joined:
            raise RuntimeError("Could not find the Jitsi join button")

        self._log_event("JOIN_CLICKED")
        logger.info("Join button clicked")

        # 5. Wait until we're actually in the meeting
        #    Jitsi doesn't have a lobby by default, so the conference should load quickly
        self._update_status("WAITING_FOR_ADMISSION")
        self._update_meeting_status("WAITING_FOR_ADMISSION")
        try:
            self._page.wait_for_selector(
                selectors.CONFERENCE_CONTAINER, timeout=30000
            )
            logger.info("Successfully joined Jitsi meeting (conference container visible)")
        except PlaywrightTimeout:
            self._check_for_errors()
            raise RuntimeError(
                "Failed to join Jitsi meeting — conference UI did not appear within 30 seconds"
            )

    # =========================================================================
    # Meeting monitoring (Jitsi-specific end signals)
    # =========================================================================

    def _is_alone(self) -> bool:
        """Check if the bot is the only participant in the Jitsi meeting by inspecting Redux state."""
        if not self._page:
            return False

        js = """
        (() => {
            try {
                if (typeof APP !== 'undefined' && APP.store) {
                    const state = APP.store.getState();
                    const participants = state['features/base/participants'];
                    if (!participants) return false;
                    
                    if (participants.remote) {
                        if (participants.remote instanceof Map) {
                            return participants.remote.size === 0;
                        }
                        return Object.keys(participants.remote).length === 0;
                    }
                    if (Array.isArray(participants)) {
                        return participants.length <= 1;
                    }
                }
            } catch(e) {
                console.error(e);
            }
            return false;
        })();
        """
        try:
            return self._page.evaluate(js)
        except Exception:
            return False

    def _monitor_meeting(self) -> None:
        """Poll for Jitsi meeting end signals.

        Checks every 5 seconds for:
        - Feedback screen (shown after hangup)
        - Kicked/removed messages
        - Welcome page (redirected after meeting ends)
        - If the bot is the only one left in the room (after others have joined)
        """
        assert self._page is not None

        logger.info("Monitoring Jitsi meeting for end signals...")
        
        has_others_joined = False

        while True:
            try:
                # Check for feedback screen (shown after leaving)
                if self._page.query_selector(selectors.FEEDBACK_SCREEN):
                    logger.info("Detected: Jitsi feedback screen (meeting ended)")
                    return

                # Check for kicked/removed
                if self._page.query_selector(selectors.KICKED_TEXT):
                    logger.info("Detected: kicked from Jitsi meeting")
                    self._log_event("REMOVED_FROM_MEETING")
                    return

                if self._page.query_selector(selectors.KICKED_TEXT_ALT):
                    logger.info("Detected: removed from Jitsi meeting")
                    self._log_event("REMOVED_FROM_MEETING")
                    return

                # Check for welcome page (redirected back)
                if self._page.query_selector(selectors.WELCOME_PAGE):
                    logger.info("Detected: Jitsi welcome page (meeting ended)")
                    return

                # Check for rejoin prompt
                if self._page.query_selector(selectors.REJOIN_BUTTON):
                    logger.info("Detected: rejoin prompt (meeting ended)")
                    return

                # Check if bot is alone
                is_alone = self._is_alone()
                if not is_alone:
                    has_others_joined = True
                elif has_others_joined and is_alone:
                    logger.info("Detected: all other participants left (bot is alone)")
                    return

            except Exception:
                # Page navigated away — meeting ended
                logger.info("Page changed — assuming Jitsi meeting ended")
                return

            self._page.wait_for_timeout(5000)

    # =========================================================================
    # Error detection (Jitsi-specific)
    # =========================================================================

    def _check_for_errors(self) -> None:
        """Check for Jitsi error states on the page."""
        assert self._page is not None

        error_selectors = [
            (selectors.MEETING_NOT_FOUND, "Jitsi meeting does not exist"),
            (selectors.MEETING_NOT_FOUND_ALT, "Jitsi meeting doesn't exist"),
            (selectors.CONNECTION_FAILED, "Jitsi connection failed"),
            (selectors.CONNECTION_FAILED_ALT, "Disconnected from Jitsi"),
        ]

        for selector, message in error_selectors:
            try:
                if self._page.query_selector(selector):
                    try:
                        self._page.screenshot(path="jitsi_error_screenshot.png")
                    except Exception as e:
                        logger.error(f"Could not take screenshot: {e}")
                    raise RuntimeError(message)
            except RuntimeError:
                raise
            except Exception:
                pass  # Selector not found — good
