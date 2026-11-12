from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import ScheduleStatus
from app.models import Assignment, Schedule, Shift, User


def get_by_id(session: Session, assignment_id: int) -> Assignment | None:
    return session.get(Assignment, assignment_id)


def list_for_schedule(session: Session, schedule_id: int) -> list[Assignment]:
    """A schedule's assignments by shift time, then employee name."""
    query = (
        select(Assignment)
        .join(Shift, Assignment.shift_id == Shift.id)
        .join(User, Assignment.user_id == User.id)
        .where(Assignment.schedule_id == schedule_id)
        .order_by(Shift.starts_at, Shift.id, User.name, Assignment.id)
    )
    return list(session.scalars(query))


def delete_for_schedule(session: Session, schedule_id: int) -> None:
    session.execute(delete(Assignment).where(Assignment.schedule_id == schedule_id))


def list_for_user_in_range(
    session: Session, user_id: int, start: datetime, end: datetime, *, published_only: bool
) -> list[tuple[Assignment, Shift, ScheduleStatus]]:
    """One user's assignments to shifts starting in [start, end), earliest first, with the status
    of the schedule each belongs to."""
    query = (
        select(Assignment, Shift, Schedule.status)
        .join(Shift, Assignment.shift_id == Shift.id)
        .join(Schedule, Assignment.schedule_id == Schedule.id)
        .where(Assignment.user_id == user_id, Shift.starts_at >= start, Shift.starts_at < end)
        .order_by(Shift.starts_at, Shift.id, Assignment.id)
    )
    if published_only:
        query = query.where(Schedule.status == ScheduleStatus.published)
    return [(assignment, shift, status) for assignment, shift, status in session.execute(query)]
