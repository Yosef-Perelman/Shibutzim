"""The audit trail of assistant tool calls (product-definition §7, principle 4)."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import ToolCallLog
from app.repositories import tool_call_log_repository


def record_tool_call(
    session: Session,
    *,
    user_id: int,
    tool: str,
    args: dict[str, Any],
    duration_ms: int,
    result_size: int,
    status: str,
) -> None:
    """Store one row and commit it, so a failed call is never missing from the log."""
    tool_call_log_repository.add(
        session,
        ToolCallLog(
            user_id=user_id,
            tool=tool,
            args=args,
            duration_ms=duration_ms,
            result_size=result_size,
            status=status,
        ),
    )
    session.commit()
