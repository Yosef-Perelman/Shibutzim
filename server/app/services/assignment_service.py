"""Manual edits of a schedule (product-definition §5.2).

The manager may add, replace or remove assignments, on a draft or a published schedule. Edits that
break **overlap** or **minimum rest** are rejected. Everything else - the employee did not say they
could work the shift, too many shifts that week, a shift staffed beyond its need - is allowed and
comes back as a warning, because the manager may know something the system does not.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import scheduler
from app.config import get_settings
from app.core.errors import Conflict, ErrorCode, NotFound, ValidationFailed
from app.models import Assignment, Schedule, Shift, User
from app.repositories import (
    assignment_repository,
    availability_repository,
    schedule_repository,
    shift_repository,
)
from app.scheduler import Constraint
from app.scheduler.explain import describe_shift
from app.services.authorization import ensure_manager
from app.services.users import ensure_assignable, get_user_or_404
from app.services.weeks import ensure_week_start

AVAILABILITY_IGNORED = "availability_ignored"
MAX_SHIFTS_EXCEEDED = "max_shifts_exceeded"
SHIFT_OVERSTAFFED = "shift_overstaffed"


@dataclass(frozen=True)
class EditWarning:
    """A rule the edit bends. The edit is saved; the manager is told."""

    code: str
    message: str


@dataclass(frozen=True)
class AssignmentEdit:
    assignment: Assignment
    user: User
    shift: Shift
    warnings: list[EditWarning]


def add_assignment(
    session: Session, current_user: User, week_start: date, *, shift_id: int, user_id: int
) -> AssignmentEdit:
    schedule = load_schedule(session, current_user, week_start)
    shift = load_week_shift(session, week_start, shift_id)
    user = get_user_or_404(session, user_id)
    ensure_assignable(user)
    edit = check_placement(session, schedule, shift, user, replacing=None)

    assignment = Assignment(schedule_id=schedule.id, shift_id=shift.id, user_id=user.id)
    save(session, assignment)
    return AssignmentEdit(assignment, user, shift, edit)


def replace_assignment(
    session: Session, current_user: User, week_start: date, assignment_id: int, *, user_id: int
) -> AssignmentEdit:
    """Give an existing assignment to another employee (the manager's "swap")."""
    schedule = load_schedule(session, current_user, week_start)
    assignment = load_assignment(session, schedule, assignment_id)
    user = get_user_or_404(session, user_id)
    ensure_assignable(user)
    shift = shift_repository.get_by_id(session, assignment.shift_id)
    warnings = check_placement(session, schedule, shift, user, replacing=assignment)

    assignment.user_id = user.id
    save(session, assignment)
    return AssignmentEdit(assignment, user, shift, warnings)


def remove_assignment(
    session: Session, current_user: User, week_start: date, assignment_id: int
) -> None:
    schedule = load_schedule(session, current_user, week_start)
    session.delete(load_assignment(session, schedule, assignment_id))
    session.commit()


# --- loading ---


def load_schedule(session: Session, current_user: User, week_start: date) -> Schedule:
    ensure_manager(current_user)
    ensure_week_start(week_start)
    schedule = schedule_repository.get_by_week(session, week_start)
    if schedule is None:
        raise NotFound(
            ErrorCode.schedule_not_found, f"There is no schedule for the week of {week_start}."
        )
    return schedule


def load_week_shift(session: Session, week_start: date, shift_id: int) -> Shift:
    shift = shift_repository.get_by_id(session, shift_id)
    if shift is None:
        raise NotFound(ErrorCode.shift_not_found, f"Shift {shift_id} does not exist.")
    if shift.week_start != week_start:
        raise ValidationFailed(
            ErrorCode.shift_not_in_week,
            f"Shift {shift_id} belongs to the week of {shift.week_start.isoformat()}.",
        )
    return shift


def load_assignment(session: Session, schedule: Schedule, assignment_id: int) -> Assignment:
    assignment = assignment_repository.get_by_id(session, assignment_id)
    if assignment is None or assignment.schedule_id != schedule.id:
        raise NotFound(
            ErrorCode.assignment_not_found, f"Assignment {assignment_id} is not in this schedule."
        )
    return assignment


# --- rules ---


def to_solver_shift(shift: Shift) -> scheduler.Shift:
    return scheduler.Shift(shift.id, shift.starts_at, shift.ends_at, shift.required_staff)


def check_placement(
    session: Session,
    schedule: Schedule,
    shift: Shift,
    user: User,
    *,
    replacing: Assignment | None,
) -> list[EditWarning]:
    """Raise for a blocking rule; return warnings for the rest. `replacing` is being given away."""
    assignments = assignment_repository.list_for_schedule(session, schedule.id)
    if any(a.shift_id == shift.id and a.user_id == user.id for a in assignments):
        raise Conflict(
            ErrorCode.already_assigned, f"{user.name} is already assigned to that shift."
        )

    week = {item.id: item for item in shift_repository.list_for_week(session, schedule.week_start)}
    zone = get_settings().tz
    others = [week[a.shift_id] for a in assignments if a.user_id == user.id]
    answer = availability_repository.get_for_user(session, user.id, [shift.id]).get(shift.id)
    rules = get_settings().scheduling_rules
    found = scheduler.constraints.violations(
        user.id,
        to_solver_shift(shift),
        [to_solver_shift(other) for other in others],
        answer.status if answer else None,
        rules,
    )

    for blocking, code in (
        (Constraint.overlap, ErrorCode.shift_overlap),
        (Constraint.min_rest, ErrorCode.min_rest_violation),
    ):
        broken = next((item for item in found if item.constraint is blocking), None)
        if broken is not None:
            raise Conflict(
                code, blocking_message(user, week[broken.shift_id], blocking, rules, zone)
            )

    when = describe_shift(to_solver_shift(shift), zone)
    warnings = []
    if any(item.constraint is Constraint.availability for item in found):
        warnings.append(
            EditWarning(AVAILABILITY_IGNORED, f"{user.name} did not mark {when} as available.")
        )
    if any(item.constraint is Constraint.max_shifts for item in found):
        warnings.append(
            EditWarning(
                MAX_SHIFTS_EXCEEDED,
                f"{user.name} now has {len(others) + 1} shifts this week; "
                f"the usual maximum is {rules.max_shifts_per_week}.",
            )
        )
    staffed = sum(1 for a in assignments if a.shift_id == shift.id and a is not replacing)
    if staffed + 1 > shift.required_staff:
        warnings.append(
            EditWarning(
                SHIFT_OVERSTAFFED,
                f"{when} now has {staffed + 1} staff; it needs {shift.required_staff}.",
            )
        )
    return warnings


def blocking_message(
    user: User, other: Shift, broken: Constraint, rules: scheduler.SchedulingRules, zone
) -> str:
    when = describe_shift(to_solver_shift(other), zone)
    if broken is Constraint.overlap:
        return f"{user.name} already works an overlapping shift on {when}."
    return (
        f"{user.name} would get less than {rules.min_rest_hours:g} hours of rest "
        f"next to the shift on {when}."
    )


def save(session: Session, assignment: Assignment) -> None:
    """Flush in a savepoint so a lost race on the unique constraint becomes `already_assigned`."""
    try:
        with session.begin_nested():
            session.add(assignment)
            session.flush()
    except IntegrityError as error:
        raise Conflict(
            ErrorCode.already_assigned, "That employee is already assigned to that shift."
        ) from error
    session.commit()
