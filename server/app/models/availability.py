from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AvailabilityStatus
from app.models.base import Base, IdMixin, text_enum


class Availability(IdMixin, Base):
    """An employee's answer for one shift; a missing row means `unavailable`."""

    __tablename__ = "availabilities"
    __table_args__ = (UniqueConstraint("shift_id", "user_id"),)

    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    status: Mapped[AvailabilityStatus] = mapped_column(
        text_enum(AvailabilityStatus, "availability_status")
    )
