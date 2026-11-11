from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Schedule


def get_by_week(session: Session, week_start: date) -> Schedule | None:
    return session.scalar(select(Schedule).where(Schedule.week_start == week_start))
