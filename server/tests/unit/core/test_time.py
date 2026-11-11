"""Work-day and week helpers. Boundaries are computed in Asia/Jerusalem (glossary §3).

Facts used below (verified with zoneinfo): Israel is UTC+2 in winter and UTC+3 in summer. In 2026
clocks move forward on Friday 2026-03-27 (a 23-hour day) and back on Sunday 2026-10-25 (25 hours).
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.time import (
    day_bounds,
    duration_seconds,
    ensure_aware,
    local_to_utc,
    shift_bounds,
    week_start,
    weekday_sunday_based,
    work_day,
)

TZ = ZoneInfo("Asia/Jerusalem")


# --- work_day ---


@pytest.mark.parametrize(
    ("instant_utc", "expected"),
    [
        (datetime(2026, 1, 15, 21, 59, tzinfo=UTC), date(2026, 1, 15)),  # 23:59 local, winter
        (datetime(2026, 1, 15, 22, 0, tzinfo=UTC), date(2026, 1, 16)),  # 00:00 local, winter
        (datetime(2026, 7, 15, 20, 59, tzinfo=UTC), date(2026, 7, 15)),  # 23:59 local, summer
        (datetime(2026, 7, 15, 21, 0, tzinfo=UTC), date(2026, 7, 16)),  # 00:00 local, summer
    ],
    ids=[
        "winter_before_midnight",
        "winter_at_midnight",
        "summer_before_midnight",
        "summer_at_midnight",
    ],
)
def test_work_day_is_the_local_date(instant_utc: datetime, expected: date) -> None:
    assert work_day(instant_utc, TZ) == expected


def test_work_day_of_an_entry_crossing_midnight_is_the_day_it_started() -> None:
    clock_in = datetime(2026, 3, 10, 22, 0, tzinfo=TZ)
    clock_out = datetime(2026, 3, 11, 6, 0, tzinfo=TZ)

    assert work_day(clock_in, TZ) == date(2026, 3, 10)
    assert work_day(clock_out, TZ) == date(
        2026, 3, 11
    )  # irrelevant for pay: entries follow clock_in


def test_work_day_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="aware"):
        work_day(datetime(2026, 3, 10, 22, 0), TZ)  # noqa: DTZ001 – the naive value is the point


# --- weeks ---


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 11, 8), date(2026, 11, 8)),  # Sunday is its own week start
        (date(2026, 11, 9), date(2026, 11, 8)),  # Monday
        (date(2026, 11, 10), date(2026, 11, 8)),  # Tuesday
        (date(2026, 11, 14), date(2026, 11, 8)),  # Saturday, last day of the week
        (date(2026, 11, 15), date(2026, 11, 15)),  # next Sunday
    ],
    ids=["sunday", "monday", "tuesday", "saturday", "next_sunday"],
)
def test_week_start_is_the_sunday_on_or_before(day: date, expected: date) -> None:
    assert week_start(day) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [(date(2026, 11, 8), 0), (date(2026, 11, 9), 1), (date(2026, 11, 14), 6)],
    ids=["sunday_is_0", "monday_is_1", "saturday_is_6"],
)
def test_weekday_sunday_based(day: date, expected: int) -> None:
    assert weekday_sunday_based(day) == expected


# --- day bounds and durations ---


def test_day_bounds_are_local_midnights_in_utc() -> None:
    start, end = day_bounds(date(2026, 1, 15), TZ)

    assert start == datetime(2026, 1, 14, 22, 0, tzinfo=UTC)
    assert end == datetime(2026, 1, 15, 22, 0, tzinfo=UTC)
    assert start.tzinfo is UTC and end.tzinfo is UTC


@pytest.mark.parametrize(
    ("day", "hours"),
    [
        (date(2026, 3, 26), 24),
        (date(2026, 3, 27), 23),  # DST starts: 02:00 -> 03:00
        (date(2026, 10, 25), 25),  # DST ends: 02:00 -> 01:00
    ],
    ids=["ordinary_day", "dst_start_day", "dst_end_day"],
)
def test_day_bounds_span_the_real_length_of_the_day(day: date, hours: int) -> None:
    start, end = day_bounds(day, TZ)

    assert duration_seconds(start, end) == hours * 3600


def test_duration_seconds_counts_elapsed_time_across_a_dst_change() -> None:
    # 22:00 Thursday to 06:00 Friday reads as 8 wall-clock hours, but the clock skipped 02:00-03:00.
    clock_in = datetime(2026, 3, 26, 22, 0, tzinfo=TZ)
    clock_out = datetime(2026, 3, 27, 6, 0, tzinfo=TZ)

    assert duration_seconds(clock_in, clock_out) == 7 * 3600


def test_duration_seconds_is_exact_to_the_second() -> None:
    start = datetime(2026, 5, 1, 8, 0, 0, tzinfo=UTC)

    assert duration_seconds(start, start + timedelta(hours=8, minutes=0, seconds=1)) == 8 * 3600 + 1


def test_ensure_aware_returns_aware_values_and_rejects_naive_ones() -> None:
    aware = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)

    assert ensure_aware(aware) is aware
    with pytest.raises(ValueError, match="aware"):
        ensure_aware(datetime(2026, 5, 1, 8, 0))  # noqa: DTZ001 – the naive value is the point


# --- local_to_utc and shift_bounds ---


@pytest.mark.parametrize(
    ("day", "at", "expected_utc"),
    [
        (date(2026, 1, 15), time(7, 0), datetime(2026, 1, 15, 5, 0, tzinfo=UTC)),  # winter, UTC+2
        (date(2026, 7, 15), time(7, 0), datetime(2026, 7, 15, 4, 0, tzinfo=UTC)),  # summer, UTC+3
        (date(2026, 1, 15), time(0, 0), datetime(2026, 1, 14, 22, 0, tzinfo=UTC)),  # local midnight
    ],
    ids=["winter", "summer", "local_midnight_is_the_previous_utc_day"],
)
def test_local_to_utc_applies_the_zone_offset_of_that_day(
    day: date, at: time, expected_utc: datetime
) -> None:
    assert local_to_utc(day, at, TZ) == expected_utc


def test_local_to_utc_returns_an_aware_utc_datetime() -> None:
    result = local_to_utc(date(2026, 1, 15), time(7, 0), TZ)

    assert result.utcoffset() == timedelta(0)


def test_shift_bounds_of_a_day_shift_stay_on_one_day() -> None:
    starts_at, ends_at = shift_bounds(date(2026, 1, 15), time(7, 0), time(15, 0), TZ)

    assert starts_at == datetime(2026, 1, 15, 5, 0, tzinfo=UTC)
    assert ends_at == datetime(2026, 1, 15, 13, 0, tzinfo=UTC)


def test_shift_bounds_with_an_end_before_the_start_end_the_next_day() -> None:
    starts_at, ends_at = shift_bounds(date(2026, 1, 15), time(23, 0), time(7, 0), TZ)

    assert starts_at == datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
    assert ends_at == datetime(2026, 1, 16, 5, 0, tzinfo=UTC)


def test_shift_bounds_with_an_end_equal_to_the_start_last_24_hours() -> None:
    starts_at, ends_at = shift_bounds(date(2026, 1, 15), time(7, 0), time(7, 0), TZ)

    assert ends_at - starts_at == timedelta(hours=24)


def test_shift_bounds_across_the_spring_forward_night_last_7_real_hours() -> None:
    # Night of Thu 2026-03-26 23:00 to Fri 03-27 07:00: clocks jump 02:00 -> 03:00 in between.
    starts_at, ends_at = shift_bounds(date(2026, 3, 26), time(23, 0), time(7, 0), TZ)

    assert starts_at == datetime(2026, 3, 26, 21, 0, tzinfo=UTC)
    assert ends_at == datetime(2026, 3, 27, 4, 0, tzinfo=UTC)
    assert ends_at - starts_at == timedelta(hours=7)


def test_shift_bounds_across_the_fall_back_night_last_9_real_hours() -> None:
    # Night of Sat 2026-10-24 23:00 to Sun 10-25 07:00: clocks fall back 02:00 -> 01:00.
    starts_at, ends_at = shift_bounds(date(2026, 10, 24), time(23, 0), time(7, 0), TZ)

    assert starts_at == datetime(2026, 10, 24, 20, 0, tzinfo=UTC)
    assert ends_at == datetime(2026, 10, 25, 5, 0, tzinfo=UTC)
    assert ends_at - starts_at == timedelta(hours=9)
