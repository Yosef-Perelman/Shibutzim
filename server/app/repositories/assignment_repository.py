from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Assignment, Shift, User


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
