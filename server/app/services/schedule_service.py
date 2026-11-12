"""Schedules: generate a draft with the solver, read it, edit it, publish it
(product-definition §5.2, architecture §6.2).

`propose_schedule` runs the solver and returns its result without saving anything; it serves the
assistant's dry run and the `debug-schedule` explanation. `generate_schedule` stores the result
as the week's draft. A published schedule is never replaced by generating again.

Both accept days off ("Dana can't work Tuesday"): a person's day off rules them out of every shift
that starts on that local day, as a hard constraint of the solver.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import scheduler
from app.config import get_settings
from app.core.enums import Role, ScheduleStatus
from app.core.errors import Conflict, ErrorCode, NotFound, ValidationFailed
from app.models import Assignment, Schedule, Shift, User
from app.repositories import (
    assignment_repository,
    availability_repository,
    schedule_repository,
    shift_repository,
    user_repository,
)
from app.scheduler.explain import explain
from app.services.authorization import ensure_manager
from app.services.weeks import ensure_week_start

WEEK_SCHEDULE_INDEX = "uq_schedules_week_start"


@dataclass(frozen=True)
class DayOff:
    """A manager's request that one employee does not work on one local day."""

    user_id: int
    day: date


@dataclass(frozen=True)
class ScheduleView:
    """A stored schedule with everything needed to show it."""

    schedule: Schedule
    shifts: list[Shift]  # the week's shifts, earliest first
    assignments: list[Assignment]  # by shift time, then employee name
    users: dict[int, User]  # the assigned employees by id


@dataclass(frozen=True)
class Proposal:
    """What the solver found for a week, with the people and shifts it was given."""

    week_start: date
    shifts: list[Shift]
    employees: list[User]
    result: scheduler.ScheduleResult
    sentences: list[str]  # one per unfilled slot, same order as `result.unfilled`


@dataclass(frozen=True)
class GeneratedSchedule:
    view: ScheduleView
    proposal: Proposal


def propose_schedule(
    session: Session,
    current_user: User,
    week_start: date,
    *,
    rules: scheduler.SchedulingRules | None = None,
    trace: bool = False,
    unavailable: Sequence[DayOff] = (),
) -> Proposal:
    """Run the solver for the week without saving. `rules` overrides the configured ones."""
    ensure_manager(current_user)
    ensure_week_start(week_start)
    return solve_week(
        session,
        week_start,
        rules or get_settings().scheduling_rules,
        trace=trace,
        unavailable=unavailable,
    )


def generate_schedule(
    session: Session,
    current_user: User,
    week_start: date,
    *,
    unavailable: Sequence[DayOff] = (),
) -> GeneratedSchedule:
    """Store the solver's result as the week's draft, replacing the current draft."""
    ensure_manager(current_user)
    ensure_week_start(week_start)
    schedule = schedule_repository.get_by_week(session, week_start)
    if schedule is not None and schedule.status is ScheduleStatus.published:
        raise Conflict(
            ErrorCode.schedule_published, "This week is already published; it cannot be generated."
        )
    proposal = solve_week(
        session, week_start, get_settings().scheduling_rules, trace=False, unavailable=unavailable
    )

    schedule = schedule or create_draft(session, week_start)
    assignment_repository.delete_for_schedule(session, schedule.id)
    session.add_all(
        Assignment(schedule_id=schedule.id, shift_id=item.shift_id, user_id=item.employee_id)
        for item in proposal.result.assignments
    )
    session.commit()
    return GeneratedSchedule(build_view(session, schedule), proposal)


def get_schedule(session: Session, current_user: User, week_start: date) -> ScheduleView:
    """Managers read any schedule; employees only a published one (a draft is not theirs to see)."""
    ensure_week_start(week_start)
    schedule = schedule_repository.get_by_week(session, week_start)
    if schedule is None or (
        current_user.role is not Role.manager and schedule.status is not ScheduleStatus.published
    ):
        raise NotFound(
            ErrorCode.schedule_not_found, f"There is no schedule for the week of {week_start}."
        )
    return build_view(session, schedule)


def publish_schedule(
    session: Session, current_user: User, week_start: date, *, now: datetime
) -> ScheduleView:
    """Make the schedule visible to employees. Later edits are visible at once (no re-publish)."""
    ensure_manager(current_user)
    ensure_week_start(week_start)
    schedule = schedule_repository.get_by_week(session, week_start)
    if schedule is None:
        raise NotFound(
            ErrorCode.schedule_not_found, f"There is no schedule for the week of {week_start}."
        )
    if schedule.status is ScheduleStatus.published:
        raise Conflict(ErrorCode.schedule_published, "This schedule is already published.")
    schedule.status = ScheduleStatus.published
    schedule.published_at = now
    session.commit()
    return build_view(session, schedule)


# --- helpers ---


def solve_week(
    session: Session,
    week_start: date,
    rules: scheduler.SchedulingRules,
    *,
    trace: bool,
    unavailable: Sequence[DayOff] = (),
) -> Proposal:
    shifts = shift_repository.list_for_week(session, week_start)
    if not shifts:
        raise ValidationFailed(
            ErrorCode.no_shifts_for_week,
            f"The week of {week_start} has no shifts; generate its shifts first.",
        )
    employees = user_repository.list_active_employees(session)
    staff_ids = {employee.id for employee in employees}
    blocks = blocks_for_days_off(unavailable, shifts, staff_ids, week_start, get_settings().tz)
    answers = availability_repository.list_for_shifts(session, [shift.id for shift in shifts])

    solver_shifts = [
        scheduler.Shift(shift.id, shift.starts_at, shift.ends_at, shift.required_staff)
        for shift in shifts
    ]
    solver_staff = [scheduler.Employee(employee.id, employee.name) for employee in employees]
    solver_answers = [
        scheduler.Availability(answer.shift_id, answer.user_id, answer.status)
        for answer in answers
        if answer.user_id in staff_ids
    ]
    try:
        result = scheduler.solve(
            solver_shifts, solver_staff, solver_answers, rules, blocks=blocks, trace=trace
        )
    except ValueError as error:
        raise ValidationFailed(ErrorCode.validation_error, str(error)) from error
    sentences = explain(result, solver_shifts, solver_staff, get_settings().tz)
    return Proposal(week_start, shifts, employees, result, sentences)


def blocks_for_days_off(
    days_off: Sequence[DayOff],
    shifts: Sequence[Shift],
    staff_ids: set[int],
    week_start: date,
    zone: ZoneInfo,
) -> list[scheduler.Block]:
    """Rule each person out of the shifts that start on their day off (local time)."""
    week_days = {week_start + timedelta(days=offset) for offset in range(7)}
    blocks: set[scheduler.Block] = set()
    for off in days_off:
        if off.user_id not in staff_ids:
            raise ValidationFailed(
                ErrorCode.user_not_assignable, f"User {off.user_id} is not an active employee."
            )
        if off.day not in week_days:
            raise ValidationFailed(
                ErrorCode.validation_error, f"{off.day} is not in the week of {week_start}."
            )
        blocks.update(
            scheduler.Block(shift.id, off.user_id)
            for shift in shifts
            if shift.starts_at.astimezone(zone).date() == off.day
        )
    return sorted(blocks, key=lambda block: (block.shift_id, block.employee_id))


def create_draft(session: Session, week_start: date) -> Schedule:
    """Insert the week's draft; if a concurrent request did first, use theirs."""
    schedule = Schedule(week_start=week_start, status=ScheduleStatus.draft, published_at=None)
    try:
        with session.begin_nested():
            session.add(schedule)
            session.flush()
    except IntegrityError as error:
        if WEEK_SCHEDULE_INDEX not in str(error.orig):
            raise
        existing = schedule_repository.get_by_week(session, week_start)
        if existing is None or existing.status is ScheduleStatus.published:
            raise Conflict(
                ErrorCode.schedule_published, "This week is already published."
            ) from error
        return existing
    return schedule


def build_view(session: Session, schedule: Schedule) -> ScheduleView:
    assignments = assignment_repository.list_for_schedule(session, schedule.id)
    users = user_repository.get_many(session, {item.user_id for item in assignments})
    return ScheduleView(
        schedule=schedule,
        shifts=shift_repository.list_for_week(session, schedule.week_start),
        assignments=assignments,
        users={user.id: user for user in users},
    )
