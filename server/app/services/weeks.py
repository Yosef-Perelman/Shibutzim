"""Rules about the scheduling week shared by the shift, availability and schedule services."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.errors import ErrorCode, ValidationFailed
from app.core.time import day_bounds
from app.core.time import week_start as week_start_of


def ensure_week_start(day: date) -> None:
    """A week is identified by its Sunday (glossary §3); any other date is a client mistake."""
    if week_start_of(day) != day:
        raise ValidationFailed(
            ErrorCode.invalid_week_start,
            f"{day.isoformat()} is not a Sunday; weeks start on Sunday.",
        )


def day_range_bounds(from_day: date, to_day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """UTC instants [start, end) covering the local days from_day..to_day inclusive."""
    if from_day > to_day:
        raise ValidationFailed(ErrorCode.validation_error, "'from' must not be after 'to'.")
    return day_bounds(from_day, zone)[0], day_bounds(to_day, zone)[1]
