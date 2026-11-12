"""Small helpers that turn service results into the compact, readable values tools return."""

from typing import Any
from zoneinfo import ZoneInfo

from app.core.time import weekday_sunday_based
from app.models import Shift
from app.pay import DayBreakdown
from app.scheduler.explain import WEEKDAY_NAMES
from app.schemas.pay import display_hours


def hours_text(seconds: int) -> str:
    """Seconds as hours with two decimals, e.g. "8.50"."""
    return str(display_hours(seconds))


def overtime_seconds(day: DayBreakdown) -> int:
    """Seconds of the day paid above the base rate."""
    return sum(line.seconds for line in day.lines if line.tier.multiplier > 1)


def shift_fields(shift: Shift, zone: ZoneInfo) -> dict[str, Any]:
    """The shift's local date, weekday, name and start and end times."""
    start = shift.starts_at.astimezone(zone)
    end = shift.ends_at.astimezone(zone)
    return {
        "date": start.date().isoformat(),
        "weekday": WEEKDAY_NAMES[weekday_sunday_based(start.date())],
        "name": shift.name,
        "start": f"{start:%H:%M}",
        "end": f"{end:%H:%M}",
    }
