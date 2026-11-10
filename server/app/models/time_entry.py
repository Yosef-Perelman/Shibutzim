from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import TimeEntrySource
from app.models.base import Base, IdMixin, text_enum


class TimeEntry(IdMixin, Base):
    """One employee's actual clock-in/out; may cross midnight; several a day form a split shift."""

    __tablename__ = "time_entries"
    __table_args__ = (
        CheckConstraint(
            "clock_out IS NULL OR clock_out > clock_in", name="clock_out_after_clock_in"
        ),
        Index("ix_time_entries_user_id_clock_in", "user_id", "clock_in"),
        # At most one open entry per employee (product-definition §5.3).
        Index(
            "uq_time_entries_one_open_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("clock_out IS NULL"),
        ),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    clock_in: Mapped[datetime]
    clock_out: Mapped[datetime | None]
    source: Mapped[TimeEntrySource] = mapped_column(text_enum(TimeEntrySource, "time_entry_source"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    note: Mapped[str | None] = mapped_column(String(500))
