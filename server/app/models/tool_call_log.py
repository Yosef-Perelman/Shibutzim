from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class ToolCallLog(IdMixin, Base):
    """Audit record of one assistant tool call."""

    __tablename__ = "tool_call_logs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    tool: Mapped[str] = mapped_column(String(100))
    args: Mapped[dict[str, Any]]
    duration_ms: Mapped[int] = mapped_column(Integer)
    result_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
