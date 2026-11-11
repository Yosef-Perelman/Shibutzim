"""Plain data the solver takes and returns. Frozen, timezone-aware, no I/O (coding-rules)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.core.enums import AvailabilityStatus
from app.core.time import ensure_aware


class Constraint(StrEnum):
    """The hard constraints a candidate can be excluded by (glossary: hard constraint)."""

    availability = "availability"
    overlap = "overlap"
    min_rest = "min_rest"
    max_shifts = "max_shifts"
    blocked = "blocked"  # the manager ruled this employee out of this shift (a requested day off)


class TraceKind(StrEnum):
    assign = "assign"  # the search placed an employee on a shift
    exclude = "exclude"  # forward checking removed a candidate from a shift
    backtrack = "backtrack"  # the search undid a placement


@dataclass(frozen=True)
class Shift:
    id: int
    starts_at: datetime
    ends_at: datetime
    required_staff: int

    def __post_init__(self) -> None:
        ensure_aware(self.starts_at)
        ensure_aware(self.ends_at)
        if self.ends_at <= self.starts_at:
            raise ValueError(f"shift {self.id} must end after it starts")
        if self.required_staff < 1:
            raise ValueError(f"shift {self.id} needs at least one staff member")

    @property
    def duration(self) -> timedelta:
        return self.ends_at - self.starts_at


@dataclass(frozen=True)
class Employee:
    id: int
    name: str


@dataclass(frozen=True)
class Availability:
    shift_id: int
    employee_id: int
    status: AvailabilityStatus


@dataclass(frozen=True)
class Block:
    """A manager's request that one employee does not work one shift, whatever they answered."""

    shift_id: int
    employee_id: int


@dataclass(frozen=True)
class Assignment:
    shift_id: int
    employee_id: int


@dataclass(frozen=True)
class Exclusion:
    """Why one employee cannot take one shift. `shift_id` is the conflicting shift, if any."""

    employee_id: int
    constraint: Constraint
    shift_id: int | None = None


@dataclass(frozen=True)
class UnfilledSlot:
    """The missing positions of one shift and why each other employee could not fill them."""

    shift_id: int
    required: int
    assigned: int
    reasons: tuple[Exclusion, ...]

    @property
    def missing(self) -> int:
        return self.required - self.assigned


@dataclass(frozen=True)
class TraceEvent:
    kind: TraceKind
    shift_id: int
    employee_id: int | None = None
    constraint: Constraint | None = None
    other_shift_id: int | None = None


@dataclass(frozen=True)
class Score:
    """Lexicographic objective: most positions filled, then the soft value (higher is better)."""

    filled: int
    preferred: int
    spread_minutes: int
    value: int

    @property
    def key(self) -> tuple[int, int]:
        return (self.filled, self.value)


@dataclass(frozen=True)
class ScheduleResult:
    assignments: tuple[Assignment, ...]
    score: Score
    unfilled: tuple[UnfilledSlot, ...]
    steps: int
    complete: bool  # False when the step budget ran out before the search finished
    trace: tuple[TraceEvent, ...] = ()
    trace_truncated: bool = False
