from collections.abc import Collection
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Availability, Shift


def list_for_week(
    session: Session, week_start: date, user_id: int | None = None
) -> list[Availability]:
    """Answers for a week's shifts (one user's, or everyone's), by shift time then user."""
    query = (
        select(Availability)
        .join(Shift, Availability.shift_id == Shift.id)
        .where(Shift.week_start == week_start)
    )
    if user_id is not None:
        query = query.where(Availability.user_id == user_id)
    order = (Shift.starts_at, Shift.id, Availability.user_id)
    return list(session.scalars(query.order_by(*order)))


def get_for_user(
    session: Session, user_id: int, shift_ids: Collection[int]
) -> dict[int, Availability]:
    """One user's existing answers for the given shifts, keyed by shift id."""
    query = select(Availability).where(
        Availability.user_id == user_id, Availability.shift_id.in_(shift_ids)
    )
    return {answer.shift_id: answer for answer in session.scalars(query)}
