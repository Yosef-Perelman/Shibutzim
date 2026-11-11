"""Availability: an employee's answer (available / preferred / unavailable) per shift of a week
(product-definition §5.1).

A shift with no answer counts as unavailable. Employees answer until a schedule exists for the
week; managers can always correct answers. Past weeks are read-only for employees.
"""

from collections.abc import Mapping
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.enums import AvailabilityStatus, Role
from app.core.errors import Conflict, ErrorCode, NotFound, ValidationFailed
from app.core.time import week_start as week_start_of
from app.models import Availability, User
from app.repositories import availability_repository, schedule_repository, shift_repository
from app.services.authorization import ensure_self_or_manager
from app.services.users import ensure_assignable, get_user_or_404
from app.services.weeks import ensure_week_start


def list_availabilities(
    session: Session, current_user: User, week_start: date, *, user_id: int | None = None
) -> list[Availability]:
    """Own answers; a manager may name a user or leave `user_id` out to read the whole team's."""
    if user_id is None and current_user.role is not Role.manager:
        user_id = current_user.id
    if user_id is not None:
        ensure_self_or_manager(current_user, user_id)
    ensure_week_start(week_start)
    if user_id is not None:
        get_user_or_404(session, user_id)
    return availability_repository.list_for_week(session, week_start, user_id)


def set_availabilities(
    session: Session,
    current_user: User,
    week_start: date,
    answers: Mapping[int, AvailabilityStatus],
    *,
    now: datetime,
    user_id: int | None = None,
) -> list[Availability]:
    """Save `answers` (shift id -> status) for one user and return all their answers that week.

    Shifts not mentioned keep their answer. Everything is validated before anything is saved.
    """
    target_id = current_user.id if user_id is None else user_id
    ensure_self_or_manager(current_user, target_id)
    ensure_week_start(week_start)
    ensure_assignable(get_user_or_404(session, target_id))
    if current_user.role is not Role.manager:
        ensure_answerable(session, week_start, now)
    ensure_shifts_in_week(session, week_start, answers)

    existing = availability_repository.get_for_user(session, target_id, list(answers))
    for shift_id, status in answers.items():
        if shift_id in existing:
            existing[shift_id].status = status
        else:
            session.add(Availability(shift_id=shift_id, user_id=target_id, status=status))
    session.commit()
    return availability_repository.list_for_week(session, week_start, target_id)


def ensure_answerable(session: Session, week_start: date, now: datetime) -> None:
    """Employees may not change answers for a finished week or one that already has a schedule."""
    today = now.astimezone(get_settings().tz).date()
    if week_start < week_start_of(today):
        raise Conflict(
            ErrorCode.availability_locked, "That week is over; its availability is read-only."
        )
    if schedule_repository.get_by_week(session, week_start) is not None:
        raise Conflict(
            ErrorCode.availability_locked,
            "A schedule already exists for that week; ask your manager to change your answers.",
        )


def ensure_shifts_in_week(
    session: Session, week_start: date, shift_ids: Mapping[int, object]
) -> None:
    found = {shift.id: shift for shift in shift_repository.get_many(session, list(shift_ids))}
    for shift_id in shift_ids:
        shift = found.get(shift_id)
        if shift is None:
            raise NotFound(ErrorCode.shift_not_found, f"Shift {shift_id} does not exist.")
        if shift.week_start != week_start:
            raise ValidationFailed(
                ErrorCode.shift_not_in_week,
                f"Shift {shift_id} belongs to the week of {shift.week_start.isoformat()}.",
            )
