from datetime import time

from sqlalchemy import Boolean, CheckConstraint, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class ShiftTemplate(IdMixin, Base):
    """Recurring slot. `end_time` at or before `start_time` means the shift ends the next day."""

    __tablename__ = "shift_templates"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("required_staff > 0", name="required_staff_positive"),
    )

    name: Mapped[str] = mapped_column(String(120))
    weekday: Mapped[int] = mapped_column(Integer)  # 0 = Sunday (glossary §3)
    start_time: Mapped[time] = mapped_column(Time)  # local time, Asia/Jerusalem
    end_time: Mapped[time] = mapped_column(Time)
    required_staff: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
