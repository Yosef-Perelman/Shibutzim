from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class Assignment(IdMixin, Base):
    """Employee X is planned for shift Y in one schedule."""

    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("schedule_id", "shift_id", "user_id"),)

    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), index=True
    )
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
