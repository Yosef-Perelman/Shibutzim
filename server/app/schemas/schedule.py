from datetime import date, datetime

from pydantic import BaseModel

from app.core.enums import ScheduleStatus
from app.scheduler import Constraint


class AssignmentOut(BaseModel):
    id: int
    shift_id: int
    user_id: int
    user_name: str
    starts_at: datetime
    ends_at: datetime


class ShiftCoverageOut(BaseModel):
    """One shift of the week and how many positions are still open in this schedule."""

    shift_id: int
    name: str
    starts_at: datetime
    ends_at: datetime
    required_staff: int
    assigned_count: int
    unfilled_count: int


class ScheduleOut(BaseModel):
    id: int
    week_start: date
    status: ScheduleStatus
    published_at: datetime | None
    assignments: list[AssignmentOut]
    shifts: list[ShiftCoverageOut]


class ReasonOut(BaseModel):
    """Why one employee could not take an unfilled shift; `shift_id` is the conflicting shift."""

    user_id: int
    user_name: str
    constraint: Constraint
    shift_id: int | None


class UnfilledSlotOut(BaseModel):
    shift_id: int
    required: int
    assigned: int
    missing: int
    reasons: list[ReasonOut]
    sentence: str


class ScoreOut(BaseModel):
    filled: int
    preferred: int
    spread_minutes: int
    value: int


class ScheduleGenerateOut(BaseModel):
    schedule: ScheduleOut
    unfilled: list[UnfilledSlotOut]
    score: ScoreOut
    complete: bool  # False when the search budget ran out before the search finished
    steps: int


class AssignmentCreate(BaseModel):
    shift_id: int
    user_id: int


class AssignmentUpdate(BaseModel):
    """Give the assignment to another employee."""

    user_id: int


class WarningOut(BaseModel):
    """A rule the edit bent; the edit was saved. Codes: availability_ignored, max_shifts_exceeded,
    shift_overstaffed."""

    code: str
    message: str


class AssignmentEditOut(BaseModel):
    assignment: AssignmentOut
    warnings: list[WarningOut]
