"""Pure scheduling module: data in, schedule out. No database, HTTP or clock (coding-rules)."""

from app.scheduler.rules import SchedulingRules
from app.scheduler.solve import solve
from app.scheduler.types import (
    Assignment,
    Availability,
    Constraint,
    Employee,
    Exclusion,
    ScheduleResult,
    Score,
    Shift,
    TraceEvent,
    TraceKind,
    UnfilledSlot,
)

__all__ = [
    "Assignment",
    "Availability",
    "Constraint",
    "Employee",
    "Exclusion",
    "ScheduleResult",
    "SchedulingRules",
    "Score",
    "Shift",
    "TraceEvent",
    "TraceKind",
    "UnfilledSlot",
    "solve",
]
