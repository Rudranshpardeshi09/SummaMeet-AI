"""Jitsi Meet CSS/ARIA selectors — centralized for easy maintenance.

Selectors target the default Jitsi Meet web UI (meet.jit.si and self-hosted).
Jitsi updates its UI less frequently than Google Meet, but keeping selectors
in one file still makes updates straightforward.
"""

from __future__ import annotations


# =============================================================================
# Pre-Join / Welcome Screen
# =============================================================================

# Display name input on the pre-join screen
NAME_INPUT = 'input[id="premeeting-name-input"], input[placeholder*="name" i]'

# "Join meeting" button on the pre-join screen
JOIN_BUTTON = 'div[data-testid="prejoin.joinMeeting"], button:has-text("Join meeting")'

# Fallback: any prominent join button
JOIN_BUTTON_FALLBACK = (
    'button:has-text("Join"), '
    'div[role="button"]:has-text("Join meeting")'
)

# Microphone and Camera toggles (we want to click them if they say "Mute" or "Stop")
MIC_TOGGLE = 'div[aria-label="Mute microphone" i], div[aria-label="Mute / Unmute" i]'
CAMERA_TOGGLE = 'div[aria-label="Stop camera" i], div[aria-label="Start / Stop camera" i]'


# =============================================================================
# In-Meeting Indicators
# =============================================================================

# The toolbar / conference container that proves we're in the call
CONFERENCE_CONTAINER = '#meet-location, div[id="videoconference_page"]'

# Hangup / leave button (red phone icon)
HANGUP_BUTTON = (
    'div[data-testid="toolbar.button.hangup"], '
    'div[aria-label="Leave" i], '
    'div[aria-label="Hang up" i]'
)

# Participant count / people panel
PARTICIPANT_COUNT = 'div[aria-label*="participant" i]'


# =============================================================================
# Meeting End / Kicked Indicators
# =============================================================================

# Feedback screen shown after leaving or being kicked
FEEDBACK_SCREEN = 'div[data-testid="feedback-location"]'

# "You have been outed" / kicked message
KICKED_TEXT = 'text="You have been outed from the meeting"'
KICKED_TEXT_ALT = 'text="You have been removed"'

# Conference ended (redirected back to welcome / blank)
WELCOME_PAGE = 'div[data-testid="welcome-location"]'

# Rejoin prompt
REJOIN_BUTTON = 'button:has-text("Rejoin"), button:has-text("OK")'


# =============================================================================
# Error States
# =============================================================================

# Meeting not found / invalid URL
MEETING_NOT_FOUND = 'text="meeting does not exist"'
MEETING_NOT_FOUND_ALT = 'text="This meeting doesn\'t exist"'

# Connection failed
CONNECTION_FAILED = 'text="Unfortunately, something went wrong"'
CONNECTION_FAILED_ALT = 'text="You have been disconnected"'


# =============================================================================
# Audio / Media Elements
# =============================================================================

MEDIA_ELEMENTS = "audio, video"
