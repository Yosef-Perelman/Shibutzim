"""Trace mode and the plain-language explanation of unfilled slots (glossary: trace, unfilled)."""

import importlib
from datetime import date, time
from zoneinfo import ZoneInfo

import pytest

from app.core.time import shift_bounds
from app.scheduler import (
    Constraint,
    Exclusion,
    ScheduleResult,
    SchedulingRules,
    Score,
    Shift,
    TraceEvent,
    TraceKind,
    UnfilledSlot,
    solve,
)
from app.scheduler.explain import describe_shift, explain
from tests.unit.scheduler.helpers import (
    AVAILABLE,
    answers,
    employees,
    everyone_available,
    make_shift,
)

solve_module = importlib.import_module("app.scheduler.solve")  # the name `solve` is the function
TZ = ZoneInfo("Asia/Jerusalem")
RULES = SchedulingRules(min_rest_hours=8, max_shifts_per_week=5)
NO_SCORE = Score(filled=0, preferred=0, spread_minutes=0, value=0)


def local_shift(shift_id: int, day: date, start: time, end: time, staff: int = 1) -> Shift:
    return Shift(shift_id, *shift_bounds(day, start, end, TZ), staff)


def result_with(*unfilled: UnfilledSlot) -> ScheduleResult:
    return ScheduleResult(assignments=(), score=NO_SCORE, unfilled=unfilled, steps=0, complete=True)


MONDAY_NIGHT = local_shift(1, date(2026, 3, 9), time(23), time(7))
TUESDAY_MORNING = local_shift(2, date(2026, 3, 10), time(7), time(15), staff=3)
STAFF = employees("Dana", "Noa", "Omer", "Tamar")


# --- trace mode ---


def week_with_a_rest_conflict():
    shifts = [MONDAY_NIGHT, TUESDAY_MORNING]
    given = answers((1, 1, AVAILABLE), (2, 1, AVAILABLE), (2, 2, AVAILABLE), (2, 3, AVAILABLE))
    return shifts, STAFF, given


def test_trace_is_empty_unless_requested() -> None:
    shifts, staff, given = week_with_a_rest_conflict()

    result = solve(shifts, staff, given, RULES)

    assert result.trace == ()
    assert result.trace_truncated is False


def test_trace_does_not_change_the_schedule() -> None:
    shifts, staff, given = week_with_a_rest_conflict()

    plain = solve(shifts, staff, given, RULES)
    traced = solve(shifts, staff, given, RULES, trace=True)

    assert traced.assignments == plain.assignments
    assert traced.score == plain.score
    assert traced.unfilled == plain.unfilled
    assert traced.trace != ()


def test_trace_records_the_availability_exclusions_of_the_input() -> None:
    shifts, staff, given = week_with_a_rest_conflict()

    trace = solve(shifts, staff, given, RULES, trace=True).trace

    assert TraceEvent(TraceKind.exclude, 2, 4, Constraint.availability) in trace
    assert TraceEvent(TraceKind.exclude, 1, 2, Constraint.availability) in trace


def test_trace_records_each_placement() -> None:
    shifts, staff, given = week_with_a_rest_conflict()

    trace = solve(shifts, staff, given, RULES, trace=True).trace

    assert TraceEvent(TraceKind.assign, 1, 1) in trace


def test_trace_names_the_shift_that_excluded_a_candidate_by_minimum_rest() -> None:
    shifts, staff, given = week_with_a_rest_conflict()

    trace = solve(shifts, staff, given, RULES, trace=True).trace

    assert TraceEvent(TraceKind.exclude, 2, 1, Constraint.min_rest, other_shift_id=1) in trace


def test_trace_records_exclusion_by_max_shifts_per_week() -> None:
    shifts = [make_shift(1, day=0), make_shift(2, day=1)]
    staff = employees("Noa")
    rules = SchedulingRules(max_shifts_per_week=1)

    trace = solve(shifts, staff, everyone_available(shifts, staff), rules, trace=True).trace

    assert any(
        event.kind is TraceKind.exclude and event.constraint is Constraint.max_shifts
        for event in trace
    )


def test_trace_records_backtracking_when_the_search_looks_for_better_coverage() -> None:
    shifts = [make_shift(1), make_shift(2), make_shift(3)]  # three concurrent shifts, two people
    staff = employees("Noa", "Omer")

    trace = solve(shifts, staff, everyone_available(shifts, staff), RULES, trace=True).trace

    assert any(event.kind is TraceKind.backtrack for event in trace)


def test_trace_stops_growing_at_its_cap_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(solve_module, "MAX_TRACE_EVENTS", 5)
    shifts, staff, given = week_with_a_rest_conflict()

    result = solve(shifts, staff, given, RULES, trace=True)

    assert len(result.trace) == 5
    assert result.trace_truncated is True


# --- describe_shift ---


def test_describe_shift_gives_the_local_weekday_and_start_time() -> None:
    assert describe_shift(TUESDAY_MORNING, TZ) == "Tuesday 07:00"


def test_describe_shift_uses_the_day_the_shift_starts_on() -> None:
    assert describe_shift(MONDAY_NIGHT, TZ) == "Monday 23:00"


def test_describe_shift_names_sunday_for_the_first_day_of_the_week() -> None:
    sunday = local_shift(3, date(2026, 3, 8), time(7), time(15))

    assert describe_shift(sunday, TZ) == "Sunday 07:00"


# --- explain ---


def test_explain_produces_the_product_sentence_for_the_documented_example() -> None:
    shifts, staff, given = week_with_a_rest_conflict()
    result = solve(shifts, staff, given, RULES)

    sentences = explain(result, shifts, staff, TZ)

    assert sentences == ["Tuesday 07:00 needs 3, only 2 available; Dana excluded by minimum rest"]


def test_explain_lists_every_excluded_employee_in_id_order() -> None:
    unfilled = UnfilledSlot(
        shift_id=2,
        required=3,
        assigned=1,
        reasons=(
            Exclusion(1, Constraint.min_rest, shift_id=1),
            Exclusion(3, Constraint.max_shifts),
        ),
    )

    sentences = explain(result_with(unfilled), [MONDAY_NIGHT, TUESDAY_MORNING], STAFF, TZ)

    assert sentences == [
        "Tuesday 07:00 needs 3, only 1 available; "
        "Dana excluded by minimum rest; Omer excluded by max shifts per week"
    ]


def test_explain_joins_several_constraints_of_one_employee() -> None:
    unfilled = UnfilledSlot(
        shift_id=2,
        required=2,
        assigned=0,
        reasons=(
            Exclusion(1, Constraint.overlap, shift_id=1),
            Exclusion(1, Constraint.max_shifts),
        ),
    )

    sentences = explain(result_with(unfilled), [MONDAY_NIGHT, TUESDAY_MORNING], STAFF, TZ)

    assert sentences == [
        "Tuesday 07:00 needs 2, only 0 available; Dana excluded by overlap and max shifts per week"
    ]


def test_explain_leaves_out_employees_who_simply_did_not_answer_available() -> None:
    unfilled = UnfilledSlot(
        shift_id=2,
        required=2,
        assigned=1,
        reasons=(Exclusion(4, Constraint.availability),),
    )

    sentences = explain(result_with(unfilled), [MONDAY_NIGHT, TUESDAY_MORNING], STAFF, TZ)

    assert sentences == ["Tuesday 07:00 needs 2, only 1 available"]


def test_explain_returns_one_sentence_per_unfilled_slot_in_order() -> None:
    first = UnfilledSlot(shift_id=1, required=1, assigned=0, reasons=())
    second = UnfilledSlot(shift_id=2, required=3, assigned=2, reasons=())

    sentences = explain(result_with(first, second), [MONDAY_NIGHT, TUESDAY_MORNING], STAFF, TZ)

    assert sentences == [
        "Monday 23:00 needs 1, only 0 available",
        "Tuesday 07:00 needs 3, only 2 available",
    ]


def test_explain_of_a_fully_staffed_week_is_empty() -> None:
    assert explain(result_with(), [MONDAY_NIGHT], STAFF, TZ) == []
