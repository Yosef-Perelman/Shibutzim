from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import TimeEntry


def get_by_id(session: Session, entry_id: int) -> TimeEntry | None:
    return session.get(TimeEntry, entry_id)


def get_open_entry(session: Session, user_id: int) -> TimeEntry | None:
    return session.scalar(
        select(TimeEntry).where(TimeEntry.user_id == user_id, TimeEntry.clock_out.is_(None))
    )


def find_overlapping(
    session: Session,
    user_id: int,
    start: datetime,
    end: datetime | None,
    *,
    exclude_id: int | None = None,
    closed_only: bool = False,
) -> TimeEntry | None:
    """An entry of `user_id` that intersects [start, end). `end=None` means open-ended.

    Intervals are half-open, so an entry ending exactly when another starts does not overlap it. An
    existing open entry extends forever. `closed_only` skips open entries, for callers where the
    unique index on open entries already decides that case.
    """
    conditions = [
        TimeEntry.user_id == user_id,
        or_(TimeEntry.clock_out.is_(None), TimeEntry.clock_out > start),
    ]
    if end is not None:
        conditions.append(TimeEntry.clock_in < end)
    if exclude_id is not None:
        conditions.append(TimeEntry.id != exclude_id)
    if closed_only:
        conditions.append(TimeEntry.clock_out.is_not(None))
    return session.scalar(select(TimeEntry).where(*conditions).limit(1))


def list_for_user(
    session: Session, user_id: int, start: datetime | None, end: datetime | None
) -> list[TimeEntry]:
    """Entries whose clock_in is in [start, end), oldest first. Either bound may be None."""
    query = select(TimeEntry).where(TimeEntry.user_id == user_id)
    if start is not None:
        query = query.where(TimeEntry.clock_in >= start)
    if end is not None:
        query = query.where(TimeEntry.clock_in < end)
    return list(session.scalars(query.order_by(TimeEntry.clock_in, TimeEntry.id)))
