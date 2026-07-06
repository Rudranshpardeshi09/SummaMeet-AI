"""Shared enumerations derived from schema design constraints.

Every CHECK constraint and status/role/type column maps to an enum here,
serving as the single source of truth across all services.
"""

from __future__ import annotations

from enum import StrEnum


# ---- Organization ----

class OrgStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


# ---- User ----

class UserRole(StrEnum):
    ADMIN = "ADMIN"
    HOST = "HOST"
    USER = "USER"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INVITED = "INVITED"
    DISABLED = "DISABLED"


# ---- Meeting ----

class MeetingPlatform(StrEnum):
    GOOGLE_MEET = "GOOGLE_MEET"


class MeetingStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    BOT_STARTING = "BOT_STARTING"
    WAITING_FOR_ADMISSION = "WAITING_FOR_ADMISSION"
    IN_PROGRESS = "IN_PROGRESS"
    PROCESSING_TRANSCRIPT = "PROCESSING_TRANSCRIPT"
    GENERATING_REPORT = "GENERATING_REPORT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ---- Meeting Participant ----

class ParticipantType(StrEnum):
    HOST = "HOST"
    USER = "USER"


class AttendanceStatus(StrEnum):
    INVITED = "INVITED"
    JOINED = "JOINED"
    ABSENT = "ABSENT"


# ---- Bot Session ----

class BotSessionStatus(StrEnum):
    QUEUED = "QUEUED"
    JOINING = "JOINING"
    WAITING_FOR_ADMISSION = "WAITING_FOR_ADMISSION"
    JOINED = "JOINED"
    RECORDING = "RECORDING"
    ENDED = "ENDED"
    FAILED = "FAILED"


# ---- Meeting Report ----

class ReportStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---- Action Item ----

class ActionItemStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    PARTIALLY_DONE = "PARTIALLY_DONE"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class ActionItemPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---- Report Artifact ----

class ArtifactType(StrEnum):
    PDF = "PDF"
    JSON_EXPORT = "JSON_EXPORT"


# ---- Audio Chunk ----

class AudioChunkFormat(StrEnum):
    WEBM = "webm"
    WAV = "wav"
    FLAC = "flac"


# ---- Bot Events ----

class BotEventType(StrEnum):
    BROWSER_LAUNCHED = "BROWSER_LAUNCHED"
    NAVIGATED = "NAVIGATED"
    LOGIN_STARTED = "LOGIN_STARTED"
    LOGIN_COMPLETED = "LOGIN_COMPLETED"
    JOIN_CLICKED = "JOIN_CLICKED"
    WAITING_IN_LOBBY = "WAITING_IN_LOBBY"
    ADMITTED = "ADMITTED"
    RECORDING_STARTED = "RECORDING_STARTED"
    RECORDING_STOPPED = "RECORDING_STOPPED"
    CHUNK_UPLOADED = "CHUNK_UPLOADED"
    MEETING_ENDED = "MEETING_ENDED"
    REMOVED_FROM_MEETING = "REMOVED_FROM_MEETING"
    ERROR = "ERROR"
    CLEANUP = "CLEANUP"

