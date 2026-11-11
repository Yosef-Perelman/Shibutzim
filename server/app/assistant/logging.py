"""Writes the tool-call log through the service layer."""

import json
import time
from typing import Any

from app.assistant.context import ToolContext
from app.services import tool_call_log_service

MILLISECONDS = 1000


def start_timer() -> float:
    return time.perf_counter()


def write_tool_call_log(
    context: ToolContext,
    *,
    tool: str,
    args: dict[str, Any],
    started: float,
    result: dict[str, Any],
    status: str,
    user_id: int,
) -> None:
    """One row per call: tool, arguments, user, duration and the size of the result."""
    tool_call_log_service.record_tool_call(
        context.session,
        user_id=user_id,
        tool=tool,
        args=args,
        duration_ms=int((time.perf_counter() - started) * MILLISECONDS),
        result_size=len(json.dumps(result, ensure_ascii=False)),
        status=status,
    )
