from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin
from app.models.shift_template import ShiftTemplate


class Shift(IdMixin, Base):
    """Concrete slot for one week; times and staff are snapshotted from the template."""

    __tablename__ = "shifts"
    __table_args__ = (
        UniqueConstraint("template_id", "week_start"),
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        CheckConstraint("required_staff > 0", name="required_staff_positive"),
        Index("ix_shifts_week_start", "week_start"),
    )

    template_id: Mapped[int] = mapped_column(
        ForeignKey("shift_templates.id", ondelete="RESTRICT"), index=True
    )
    week_start: Mapped[date] = mapped_column(Date)
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    required_staff: Mapped[int] = mapped_column(Integer)

    template: Mapped[ShiftTemplate] = relationship(lazy="joined")

    @property
    def name(self) -> str:
        """The template's name: what the shift is called on screen."""
        return self.template.name
