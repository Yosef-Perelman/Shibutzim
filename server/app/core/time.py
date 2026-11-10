"""Work-day and week helpers.

Boundaries are computed in the configured zone (`Asia/Jerusalem`); storage and arithmetic use UTC
(product-definition §6.3, glossary §3). Every datetime must be timezone-aware; a naive one is a bug.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DAYS_PER_WEEK = 7


def ensure_aware(moment: datetime) -> datetime:
    """Return `moment` unchanged if it is timezone-aware; raise `ValueError` otherwise."""
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise ValueError(f"datetime must be timezone-aware, got naive {moment.isoformat()}")
    return moment


def work_day(moment: datetime, tz: ZoneInfo) -> date:
    """The local calendar date of `moment`. A time entry's work day is that of its clock_in."""
    return ensure_aware(moment).astimezone(tz).date()


def weekday_sunday_based(day: date) -> int:
    """0 = Sunday … 6 = Saturday (glossary §3), unlike `date.weekday()` where Monday is 0."""
    return (day.weekday() + 1) % DAYS_PER_WEEK


def week_start(day: date) -> date:
    """The Sunday on or before `day`; identifies the scheduling week."""
    return day - timedelta(days=weekday_sunday_based(day))


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Local midnight starting `day` and local midnight starting the next day, both as UTC instants.

    The span is 23 or 25 hours on the days the clocks change.
    """
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def duration_seconds(start: datetime, end: datetime) -> int:
    """Elapsed seconds between two instants, measured in UTC so a DST change cannot distort it."""
    delta = ensure_aware(end).astimezone(UTC) - ensure_aware(start).astimezone(UTC)
    return int(delta.total_seconds())
