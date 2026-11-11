"""Scheduler value objects validate their input (pure module: ValueError for impossible data)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings
from app.scheduler import SchedulingRules, Shift

START = datetime(2026, 3, 9, 5, 0, tzinfo=UTC)


# --- SchedulingRules ---


def test_default_rules_match_the_product_definition() -> None:
    rules = SchedulingRules.default()

    assert rules.min_rest_hours == 8
    assert rules.max_shifts_per_week == 5
    assert rules.max_steps == 200_000


def test_min_rest_is_the_hours_as_a_timedelta() -> None:
    assert SchedulingRules(min_rest_hours=7.5).min_rest == timedelta(hours=7, minutes=30)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_rest_hours": -1},
        {"max_shifts_per_week": 0},
        {"max_steps": 0},
    ],
    ids=["negative_rest", "zero_max_shifts", "zero_max_steps"],
)
def test_rules_reject_impossible_values(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        SchedulingRules(**kwargs)


def test_zero_minimum_rest_is_allowed() -> None:
    assert SchedulingRules(min_rest_hours=0).min_rest == timedelta(0)


def test_settings_build_the_rules_from_scheduler_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEDULER_MIN_REST_HOURS", "10")
    monkeypatch.setenv("SCHEDULER_MAX_SHIFTS_PER_WEEK", "4")
    monkeypatch.setenv("SCHEDULER_MAX_STEPS", "1000")

    rules = Settings().scheduling_rules

    assert rules == SchedulingRules(min_rest_hours=10, max_shifts_per_week=4, max_steps=1000)


def test_settings_default_to_the_default_rules() -> None:
    assert Settings().scheduling_rules == SchedulingRules.default()


# --- Shift ---


def test_shift_duration_is_end_minus_start() -> None:
    shift = Shift(id=1, starts_at=START, ends_at=START + timedelta(hours=8), required_staff=2)

    assert shift.duration == timedelta(hours=8)


def test_shift_rejects_an_end_at_or_before_the_start() -> None:
    with pytest.raises(ValueError):
        Shift(id=1, starts_at=START, ends_at=START, required_staff=1)


def test_shift_rejects_naive_datetimes() -> None:
    naive = datetime(2026, 3, 9, 7, 0)  # noqa: DTZ001 - the point of the test
    with pytest.raises(ValueError):
        Shift(id=1, starts_at=naive, ends_at=naive + timedelta(hours=8), required_staff=1)


def test_shift_rejects_zero_required_staff() -> None:
    with pytest.raises(ValueError):
        Shift(id=1, starts_at=START, ends_at=START + timedelta(hours=8), required_staff=0)
