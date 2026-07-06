"""Google Meet CSS/ARIA selectors — centralized for easy maintenance.

Google frequently changes their UI, so keeping selectors in one file
makes updates straightforward. Each selector group is documented with
the expected UI context.
"""

from __future__ import annotations


# =============================================================================
# Pre-Join Screen (the page shown before entering the meeting)
# =============================================================================

# "Your name" input field shown to guests
NAME_INPUT = 'input[aria-label="Your name"]'

# Microphone toggle button
MIC_TOGGLE = '[aria-label*="microphone" i]'

# Camera toggle button
CAMERA_TOGGLE = '[aria-label*="camera" i]'

# "Ask to join" / "Join now" button
JOIN_BUTTON = 'button[jsname="Qx7uuf"]'
JOIN_BUTTON_FALLBACK = 'button:has-text("Ask to join"), button:has-text("Join now")'

# "Got it" / dismiss buttons for various prompts
DISMISS_BUTTON = 'button:has-text("Got it"), button:has-text("Dismiss")'
# =============================================================================
# Google Sign-In (when the bot needs to authenticate)
# =============================================================================

GOOGLE_EMAIL_INPUT = 'input[type="email"], input[name="identifier"], #identifierId'
GOOGLE_EMAIL_NEXT = '#identifierNext button, button:has-text("Next")'
GOOGLE_PASSWORD_INPUT = 'input[type="password"], input[name="password"], input[name="Passwd"]'
GOOGLE_PASSWORD_NEXT = '#passwordNext button, button:has-text("Next")'




# =============================================================================
# Lobby / Waiting Room
# =============================================================================

# Text shown when waiting for host to admit
LOBBY_TEXT = 'text="Asking to be let in"'
LOBBY_TEXT_ALT = 'text="Someone will let you in soon"'

# Indicator that we've been admitted (meeting toolbar appears)
MEETING_TOOLBAR = '[data-call-ended="false"]'
IN_MEETING_INDICATOR = '[data-meeting-title]'


# =============================================================================
# In-Meeting Indicators
# =============================================================================

# Participant count badge
PARTICIPANT_COUNT = '[aria-label*="participant" i]'

# Meeting timer / duration
MEETING_TIMER = '[data-meeting-timer]'

# End call / leave button
END_CALL_BUTTON = '[aria-label="Leave call" i]'
END_CALL_BUTTON_ALT = 'button[aria-label*="leave" i]'


# =============================================================================
# Meeting End / Removal Indicators
# =============================================================================

# "You've been removed from the meeting"
REMOVED_TEXT = 'text="You\'ve been removed from the meeting"'

# "The meeting has ended"  / "You left the meeting"
MEETING_ENDED_TEXT = 'text="The meeting has ended"'
LEFT_MEETING_TEXT = 'text="You left the meeting"'

# "Return to home screen" button (appears after meeting ends)
RETURN_HOME_BUTTON = 'button:has-text("Return to home screen")'
REJOIN_BUTTON = 'button:has-text("Rejoin")'


# =============================================================================
# Error States
# =============================================================================

# "Meeting not found" / "Invalid meeting link"
MEETING_NOT_FOUND = 'text="Check your meeting code"'
MEETING_NOT_FOUND_ALT = 'text="meeting doesn\'t exist"'

# "You can\'t join this meeting" (permissions / org restrictions)
CANNOT_JOIN = 'text="You can\'t join this video call"'
CANNOT_JOIN_ALT = 'text="You are not allowed to join"'


# =============================================================================
# Audio Element (for CDPSession audio capture)
# =============================================================================

# The main audio/video elements in a Meet session
MEDIA_ELEMENTS = "audio, video"
