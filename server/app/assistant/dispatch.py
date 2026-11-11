"""Runs one tool call: role check, argument validation, the tool itself, and the log.

`call_tool` never raises for a problem the model can explain (unknown tool, wrong role, bad
arguments, a domain error): it returns a structured result with an `error`. The one exception is a
provider outage (`ServiceUnavailable`), which is logged and raised so the endpoint can answer 503.
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from app.assistant.context import ToolContext
from app.assistant.logging import start_timer, write_tool_call_log
from app.assistant.tools import registry
from app.core.errors import DomainError, ErrorCode, ServiceUnavailable

logger = logging.getLogger("app.assistant")

Status = Literal["ok", "error", "refused"]
UNEXPECTED_MESSAGE = "The tool failed unexpectedly. Tell the user you could not look that up."


@dataclass(frozen=True)
class ToolOutcome:
    content: dict[str, Any]  # what the model sees
    status: Status
    proposal: dict[str, Any] | None = None  # a write tool's full proposal, for the UI only


def call_tool(context: ToolContext, name: str, args: dict[str, Any]) -> ToolOutcome:
    user_id = context.user.id
    started = start_timer()
    try:
        outcome = execute(context, name, args)
    except ServiceUnavailable:
        write_tool_call_log(
            context,
            tool=name,
            args=args,
            started=started,
            result={},
            status="error",
            user_id=user_id,
        )
        raise
    write_tool_call_log(
        context,
        tool=name,
        args=args,
        started=started,
        result=outcome.content,
        status=outcome.status,
        user_id=user_id,
    )
    return outcome


def execute(context: ToolContext, name: str, args: dict[str, Any]) -> ToolOutcome:
    tool = registry.get_tool(name)
    if tool is None:
        return failure("unknown_tool", f"There is no tool called {name}.", "refused")
    if context.user.role not in tool.roles:
        return failure("forbidden", "This tool is not available for the user's role.", "refused")
    try:
        arguments = tool.arguments.model_validate(args)
    except ValidationError as error:
        return failure(ErrorCode.validation_error, describe_problems(error), "error")
    try:
        content = tool.run(context, arguments)
        proposal = content.pop("proposal", None) if tool.writes else None
        return ToolOutcome(content, "ok", proposal)
    except ServiceUnavailable:
        raise
    except DomainError as error:
        return failure(error.code, error.message, "error")
    except Exception:
        logger.exception("Assistant tool %s failed", name)
        context.session.rollback()
        return failure(ErrorCode.internal_error, UNEXPECTED_MESSAGE, "error")


def failure(code: str, message: str, status: Status) -> ToolOutcome:
    return ToolOutcome({"error": {"code": str(code), "message": message}}, status)


def describe_problems(error: ValidationError) -> str:
    """The invalid fields in plain words, so the model can correct the call."""
    return "; ".join(
        f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
        for problem in error.errors()
    )
