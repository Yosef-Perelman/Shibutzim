"""Rules about the scheduling week shared by the shift, availability and schedule services."""

from datetime import date

from app.core.errors import ErrorCode, ValidationFailed
from app.core.time import week_start as week_start_of


def ensure_week_start(day: date) -> None:
    """A week is identified by its Sunday (glossary §3); any other date is a client mistake."""
    if week_start_of(day) != day:
        raise ValidationFailed(
            ErrorCode.invalid_week_start,
            f"{day.isoformat()} is not a Sunday; weeks start on Sunday.",
        )
