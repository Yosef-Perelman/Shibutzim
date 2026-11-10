"""All models, imported here so Alembic's autogenerate sees every table (database-rules)."""

from app.models.assignment import Assignment
from app.models.availability import Availability
from app.models.base import Base
from app.models.handbook_chunk import HandbookChunk
from app.models.schedule import Schedule
from app.models.shift import Shift
from app.models.shift_template import ShiftTemplate
from app.models.time_entry import TimeEntry
from app.models.tool_call_log import ToolCallLog
from app.models.user import User

__all__ = [
    "Assignment",
    "Availability",
    "Base",
    "HandbookChunk",
    "Schedule",
    "Shift",
    "ShiftTemplate",
    "TimeEntry",
    "ToolCallLog",
    "User",
]
