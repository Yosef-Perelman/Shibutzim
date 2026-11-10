"""Time tracking: clock in/out, manager corrections, listing (product-definition §5.3).

Rules enforced here: one open entry per employee, clock-out after clock-in, no entry longer than 24
hours, and no overlap between an employee's entries (an overlap would double-count pay).
"""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.enums import TimeEntrySource
from app.core.errors import Conflict, ErrorCode, NotFound, ValidationFailed
from app.core.time import day_bounds
from app.models import TimeEntry, User
from app.repositories import time_entry_repository, user_repository
from app.services.authorization import ensure_manager, ensure_self_or_manager

MAX_ENTRY_DURATION = timedelta(hours=24)
OPEN_ENTRY_INDEX = "uq_time_entries_one_open_per_user"
UPDATABLE_FIELDS = ("clock_in", "clock_out", "note")


# --- employee actions ---


def clock_in(session: Session, current_user: User, *, now: datetime) -> TimeEntry:
    if time_entry_repository.get_open_entry(session, current_user.id):
        raise Conflict(ErrorCode.already_clocked_in, "You are already clocked in.")
    # Open entries are decided by the unique index; only closed entries reaching past `now` count.
    ensure_no_overlap(session, current_user.id, now, None, closed_only=True)

    entry = TimeEntry(
        user_id=current_user.id,
        clock_in=now,
        clock_out=None,
        source=TimeEntrySource.clock,
        created_by=current_user.id,
    )
    try:
        with session.begin_nested():
            session.add(entry)
            session.flush()
    except IntegrityError as error:
        # Two simultaneous requests can both pass the check above; the unique index stops one.
        if OPEN_ENTRY_INDEX in str(error.orig):
            raise Conflict(ErrorCode.already_clocked_in, "You are already clocked in.") from error
        raise
    session.commit()
    return entry


def clock_out(session: Session, current_user: User, *, now: datetime) -> TimeEntry:
    entry = time_entry_repository.get_open_entry(session, current_user.id)
    if entry is None:
        raise Conflict(ErrorCode.not_clocked_in, "You are not clocked in.")
    validate_interval(entry.clock_in, now)
    ensure_no_overlap(session, current_user.id, entry.clock_in, now, exclude_id=entry.id)

    entry.clock_out = now
    session.commit()
    return entry


# --- reading ---


def list_time_entries(
    session: Session,
    current_user: User,
    *,
    user_id: int | None = None,
    from_day: date | None = None,
    to_day: date | None = None,
) -> list[TimeEntry]:
    """Entries of `user_id` (default: the current user) whose work day is in [from_day, to_day]."""
    target_id = current_user.id if user_id is None else user_id
    ensure_self_or_manager(current_user, target_id)
    ensure_user_exists(session, target_id)
    if from_day and to_day and from_day > to_day:
        raise ValidationFailed(ErrorCode.validation_error, "'from' must not be after 'to'.")

    zone = get_settings().tz
    start = day_bounds(from_day, zone)[0] if from_day else None
    end = day_bounds(to_day, zone)[1] if to_day else None
    return time_entry_repository.list_for_user(session, target_id, start, end)


# --- manager actions ---


def create_time_entry(
    session: Session,
    current_user: User,
    *,
    user_id: int,
    clock_in: datetime,
    clock_out: datetime,
    note: str | None = None,
) -> TimeEntry:
    ensure_manager(current_user)
    ensure_user_exists(session, user_id)
    validate_interval(clock_in, clock_out)
    ensure_no_overlap(session, user_id, clock_in, clock_out)

    entry = TimeEntry(
        user_id=user_id,
        clock_in=clock_in,
        clock_out=clock_out,
        source=TimeEntrySource.manual,
        created_by=current_user.id,
        note=note,
    )
    session.add(entry)
    session.commit()
    return entry


def update_time_entry(
    session: Session, current_user: User, entry_id: int, *, changes: dict[str, Any]
) -> TimeEntry:
    """Apply the given changes; the merged interval is validated as a whole."""
    ensure_manager(current_user)
    entry = get_entry_or_404(session, entry_id)
    new_in = changes.get("clock_in", entry.clock_in)
    new_out = changes.get("clock_out", entry.clock_out)
    if new_out is not None:
        validate_interval(new_in, new_out)
    ensure_no_overlap(
        session, entry.user_id, new_in, new_out, exclude_id=entry.id, closed_only=new_out is None
    )

    for field in UPDATABLE_FIELDS:
        if field in changes:
            setattr(entry, field, changes[field])
    session.commit()
    return entry


def delete_time_entry(session: Session, current_user: User, entry_id: int) -> None:
    ensure_manager(current_user)
    session.delete(get_entry_or_404(session, entry_id))
    session.commit()


# --- shared rules ---


def get_entry_or_404(session: Session, entry_id: int) -> TimeEntry:
    entry = time_entry_repository.get_by_id(session, entry_id)
    if entry is None:
        raise NotFound(ErrorCode.time_entry_not_found, f"Time entry {entry_id} does not exist.")
    return entry


def ensure_user_exists(session: Session, user_id: int) -> None:
    if user_repository.get_by_id(session, user_id) is None:
        raise NotFound(ErrorCode.user_not_found, f"User {user_id} does not exist.")


def validate_interval(clock_in: datetime, clock_out: datetime) -> None:
    if clock_out <= clock_in:
        raise ValidationFailed(
            ErrorCode.clock_out_before_clock_in, "Clock-out must be after clock-in."
        )
    if clock_out - clock_in > MAX_ENTRY_DURATION:
        raise ValidationFailed(
            ErrorCode.entry_too_long,
            "A time entry cannot be longer than 24 hours. Ask a manager to correct it.",
        )


def ensure_no_overlap(
    session: Session,
    user_id: int,
    start: datetime,
    end: datetime | None,
    *,
    exclude_id: int | None = None,
    closed_only: bool = False,
) -> None:
    found = time_entry_repository.find_overlapping(
        session, user_id, start, end, exclude_id=exclude_id, closed_only=closed_only
    )
    if found is not None:
        raise Conflict(
            ErrorCode.time_entry_overlap,
            "This entry overlaps another time entry of the same employee.",
        )
