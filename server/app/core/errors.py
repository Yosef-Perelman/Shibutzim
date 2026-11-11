"""Domain errors and the error-code catalogue.

Services raise these; one handler in `app.main` maps them to HTTP responses of one shape,
`{"error": {"code", "message"[, "details"]}}` (error-handling-rules). Routers never catch them.
"""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Every stable error code the API can return. New codes go here and in error-handling-rules."""

    # 422
    validation_error = "validation_error"
    clock_out_before_clock_in = "clock_out_before_clock_in"
    entry_too_long = "entry_too_long"
    invalid_week_start = "invalid_week_start"
    # 401
    invalid_credentials = "invalid_credentials"
    invalid_token = "invalid_token"
    token_expired = "token_expired"
    # 403
    forbidden = "forbidden"
    # 404
    user_not_found = "user_not_found"
    time_entry_not_found = "time_entry_not_found"
    shift_template_not_found = "shift_template_not_found"
    # 409
    already_clocked_in = "already_clocked_in"
    not_clocked_in = "not_clocked_in"
    time_entry_overlap = "time_entry_overlap"
    # 500
    internal_error = "internal_error"


class DomainError(Exception):
    """Base class: subclasses fix the HTTP status and default code; instances carry the message."""

    status_code: int = 500
    default_code: ErrorCode = ErrorCode.internal_error

    def __init__(
        self,
        code: ErrorCode | None = None,
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = str(code or self.default_code)
        self.message = message or self.code.replace("_", " ").capitalize() + "."
        self.details = details
        super().__init__(self.message)

    def to_body(self) -> dict[str, Any]:
        return error_body(self.code, self.message, self.details)


class ValidationFailed(DomainError):
    status_code = 422
    default_code = ErrorCode.validation_error


class Unauthorized(DomainError):
    status_code = 401
    default_code = ErrorCode.invalid_credentials


class Forbidden(DomainError):
    status_code = 403
    default_code = ErrorCode.forbidden


class NotFound(DomainError):
    status_code = 404
    default_code = ErrorCode.user_not_found


class Conflict(DomainError):
    status_code = 409
    default_code = ErrorCode.already_clocked_in


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}
