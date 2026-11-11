"""Hard constraints in isolation: availability, overlap, minimum rest, max shifts per week."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.scheduler import Constraint, Exclusion, SchedulingRules
from app.scheduler.constraints import conflict, overlaps, rest_gap, violations
from tests.unit.scheduler.helpers import AVAILABLE, PREFERRED, UNAVAILABLE, make_shift

RULES = SchedulingRules(min_rest_hours=8, max_shifts_per_week=5)
EMPLOYEE = 7


# --- overlaps (half-open intervals) ---


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (make_shift(1, hour=7, hours=8), make_shift(2, hour=10, hours=8), True),  # partial
        (make_shift(1, hour=7, hours=8), make_shift(2, hour=9, hours=2), True),  # contained
        (make_shift(1, hour=7, hours=8), make_shift(2, hour=7, hours=8), True),  # identical
        (make_shift(1, hour=7, hours=8), make_shift(2, hour=15, hours=8), False),  # touching
        (make_shift(1, hour=7, hours=8), make_shift(2, day=1, hour=7, hours=8), False),  # apart
    ],
    ids=["partial", "contained", "identical", "touching_end_to_start", "different_days"],
)
def test_overlaps(a, b, expected) -> None:
    assert overlaps(a, b) is expected
    assert overlaps(b, a) is expected


# --- rest_gap and conflict ---


def test_rest_gap_is_the_time_between_the_earlier_end_and_the_later_start() -> None:
    morning = make_shift(1, hour=7, hours=8)  # 07-15
    next_morning = make_shift(2, day=1, hour=7, hours=8)

    assert rest_gap(morning, next_morning) == timedelta(hours=16)
    assert rest_gap(next_morning, morning) == timedelta(hours=16)


def test_rest_gap_of_overlapping_shifts_is_negative() -> None:
    assert rest_gap(make_shift(1, hour=7, hours=8), make_shift(2, hour=10, hours=8)) < timedelta(0)


@pytest.mark.parametrize(
    ("second", "min_rest_hours", "expected"),
    [
        (make_shift(2, hour=15, hours=8), 8, Constraint.min_rest),  # no gap at all
        (make_shift(2, hour=22, hours=8), 8, Constraint.min_rest),  # 7 h
        (make_shift(2, hour=22, hours=8), 7, None),  # exactly 7 h with a 7 h rule
        (make_shift(2, day=1, hour=7, hours=8), 8, None),  # 16 h
        (make_shift(2, hour=10, hours=8), 8, Constraint.overlap),  # overlap wins over rest
        (make_shift(2, hour=15, hours=8), 0, None),  # touching is fine without a rest rule
    ],
    ids=["touching", "seven_hours", "exactly_the_rule", "sixteen_hours", "overlap", "zero_rest"],
)
def test_conflict(second, min_rest_hours, expected) -> None:
    first = make_shift(1, hour=7, hours=8)  # 07-15

    assert conflict(first, second, SchedulingRules(min_rest_hours=min_rest_hours)) is expected


def test_rest_of_exactly_the_minimum_passes_and_one_minute_less_fails() -> None:
    first = make_shift(1, hour=7, hours=8)  # ends 15:00
    exactly = make_shift(2, hour=23, hours=4)  # starts 23:00, gap 8 h
    one_minute_short = replace(exactly, starts_at=exactly.starts_at - timedelta(minutes=1))

    assert conflict(first, exactly, RULES) is None
    assert conflict(first, one_minute_short, RULES) is Constraint.min_rest


# --- violations ---


def test_no_violation_for_an_available_employee_with_nothing_else_assigned() -> None:
    assert violations(EMPLOYEE, make_shift(1), [], AVAILABLE, RULES) == []


def test_a_preferred_answer_is_not_a_violation() -> None:
    assert violations(EMPLOYEE, make_shift(1), [], PREFERRED, RULES) == []


@pytest.mark.parametrize("status", [UNAVAILABLE, None], ids=["unavailable", "no_answer"])
def test_unavailable_or_no_answer_violates_availability(status) -> None:
    result = violations(EMPLOYEE, make_shift(1), [], status, RULES)

    assert result == [Exclusion(EMPLOYEE, Constraint.availability)]


def test_an_overlapping_assigned_shift_violates_overlap_and_is_named() -> None:
    other = make_shift(2, hour=10, hours=8)

    result = violations(EMPLOYEE, make_shift(1, hour=7, hours=8), [other], AVAILABLE, RULES)

    assert result == [Exclusion(EMPLOYEE, Constraint.overlap, shift_id=2)]


def test_a_shift_too_close_violates_min_rest_and_is_named() -> None:
    evening = make_shift(2, hour=15, hours=8)

    result = violations(EMPLOYEE, make_shift(1, hour=7, hours=8), [evening], AVAILABLE, RULES)

    assert result == [Exclusion(EMPLOYEE, Constraint.min_rest, shift_id=2)]


def test_the_sixth_shift_of_the_week_violates_max_shifts() -> None:
    assigned = [make_shift(10 + day, day=day) for day in range(5)]

    result = violations(EMPLOYEE, make_shift(1, day=5), assigned, AVAILABLE, RULES)

    assert result == [Exclusion(EMPLOYEE, Constraint.max_shifts)]


def test_the_fifth_shift_of_the_week_is_allowed() -> None:
    assigned = [make_shift(10 + day, day=day) for day in range(4)]

    assert violations(EMPLOYEE, make_shift(1, day=5), assigned, AVAILABLE, RULES) == []


def test_the_candidate_shift_itself_in_the_assigned_list_is_ignored() -> None:
    shift = make_shift(1)

    assert violations(EMPLOYEE, shift, [shift], AVAILABLE, RULES) == []


def test_every_violated_constraint_is_reported() -> None:
    assigned = [make_shift(10, hour=10, hours=8)] + [
        make_shift(20 + d, day=d + 1) for d in range(4)
    ]

    result = violations(EMPLOYEE, make_shift(1, hour=7, hours=8), assigned, UNAVAILABLE, RULES)

    assert [item.constraint for item in result] == [
        Constraint.availability,
        Constraint.overlap,
        Constraint.max_shifts,
    ]
