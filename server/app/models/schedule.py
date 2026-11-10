from datetime import date, datetime

from sqlalchemy import Date
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ScheduleStatus
from app.models.base import Base, IdMixin, text_enum


class Schedule(IdMixin, Base):
    """One schedule per week."""

    __tablename__ = "schedules"

    week_start: Mapped[date] = mapped_column(Date, unique=True)
    status: Mapped[ScheduleStatus] = mapped_column(text_enum(ScheduleStatus, "schedule_status"))
    published_at: Mapped[datetime | None]
