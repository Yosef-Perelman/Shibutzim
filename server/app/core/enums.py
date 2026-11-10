"""Domain enums (glossary §2). Stored as text with a CHECK constraint (database-rules)."""

from enum import StrEnum


class Role(StrEnum):
    manager = "manager"
    employee = "employee"


class AvailabilityStatus(StrEnum):
    available = "available"
    preferred = "preferred"
    unavailable = "unavailable"


class ScheduleStatus(StrEnum):
    draft = "draft"
    published = "published"


class TimeEntrySource(StrEnum):
    clock = "clock"
    manual = "manual"
