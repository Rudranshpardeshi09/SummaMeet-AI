"""Tests for shared contract enums."""

from __future__ import annotations

from contracts.enums import (
    UserRole,
    UserStatus,
    MeetingStatus,
    BotSessionStatus,
    ReportStatus,
    ActionItemPriority,
)


class TestEnums:
    """Verify enum values match schema CHECK constraints exactly."""

    def test_user_roles(self):
        assert set(UserRole) == {"ADMIN", "HOST", "USER"}

    def test_user_statuses(self):
        assert set(UserStatus) == {"ACTIVE", "INVITED", "DISABLED"}

    def test_meeting_statuses(self):
        expected = {
            "SCHEDULED",
            "BOT_STARTING",
            "WAITING_FOR_ADMISSION",
            "IN_PROGRESS",
            "PROCESSING_TRANSCRIPT",
            "GENERATING_REPORT",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
        }
        assert set(MeetingStatus) == expected

    def test_bot_session_statuses(self):
        expected = {
            "QUEUED",
            "JOINING",
            "WAITING_FOR_ADMISSION",
            "JOINED",
            "RECORDING",
            "ENDED",
            "FAILED",
        }
        assert set(BotSessionStatus) == expected

    def test_report_statuses(self):
        assert set(ReportStatus) == {"NOT_STARTED", "IN_PROGRESS", "COMPLETED", "FAILED"}

    def test_action_item_priorities(self):
        assert set(ActionItemPriority) == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    def test_enum_string_values(self):
        """StrEnum values should be usable as plain strings."""
        assert UserRole.ADMIN == "ADMIN"
        assert str(UserRole.HOST) == "HOST"
