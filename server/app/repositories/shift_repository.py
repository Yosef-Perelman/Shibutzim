from collections.abc import Collection
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Shift


def get_by_id(session: Session, shift_id: int) -> Shift | None:
    return session.get(Shift, shift_id)


def get_many(session: Session, shift_ids: Collection[int]) -> list[Shift]:
    return list(session.scalars(select(Shift).where(Shift.id.in_(shift_ids))))


def list_for_week(session: Session, week_start: date) -> list[Shift]:
    """A week's shifts, earliest first."""
    query = select(Shift).where(Shift.week_start == week_start)
    return list(session.scalars(query.order_by(Shift.starts_at, Shift.id)))
