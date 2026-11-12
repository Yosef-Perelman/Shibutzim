"""The solver: mandatory matrix of testing-rules plus boundaries.

Matrix: no solution, tight solution, fairness, each hard constraint in isolation (availability,
required staff, overlap, minimum rest, max shifts per week), preferred shifts honored when possible.
"""

import random
import time as clock
from collections import defaultdict
from datetime import date, time
from zoneinfo import ZoneInfo

import pytest

from app.core.time import shift_bounds
from app.scheduler import (
    Availability,
    Block,
    Constraint,
    Exclusion,
    SchedulingRules,
    Shift,
    solve,
)
from app.scheduler.scoring import PREFERRED_WEIGHT
from tests.unit.scheduler.helpers import (
    AVAILABLE,
    PREFERRED,
    UNAVAILABLE,
    answers,
    assert_hard_constraints,
    best_coverage,
    employees,
    everyone_available,
    make_shift,
)

RULES = SchedulingRules(min_rest_hours=8, max_shifts_per_week=5)
TZ = ZoneInfo("Asia/Jerusalem")


def staffed(result) -> dict[int, set[int]]:
    """shift id -> ids of the employees assigned to it."""
    found: dict[int, set[int]] = defaultdict(set)
    for assignment in result.assignments:
        found[assignment.shift_id].add(assignment.employee_id)
    return found


def hours_by_employee(result, shifts) -> dict[int, float]:
    by_id = {shift.id: shift for shift in shifts}
    totals: dict[int, float] = defaultdict(float)
    for assignment in result.assignments:
        totals[assignment.employee_id] += by_id[assignment.shift_id].duration.total_seconds() / 3600
    return dict(totals)


# --- degenerate input ---


def test_solve_with_no_shifts_returns_an_empty_complete_result() -> None:
    result = solve([], employees("Noa"), [], RULES)

    assert result.assignments == ()
    assert result.unfilled == ()
    assert result.score.filled == 0
    assert result.complete is True


def test_solve_with_no_employees_leaves_every_position_unfilled() -> None:
    shift = make_shift(1, staff=2)

    result = solve([shift], [], [], RULES)

    assert result.assignments == ()
    assert [(u.shift_id, u.required, u.assigned, u.reasons) for u in result.unfilled] == [
        (1, 2, 0, ())
    ]


def test_solve_with_a_shift_nobody_answered_for_reports_availability_for_everyone() -> None:
    staff = employees("Noa", "Omer")

    result = solve([make_shift(1)], staff, [], RULES)

    assert result.assignments == ()
    assert result.unfilled[0].reasons == (
        Exclusion(1, Constraint.availability),
        Exclusion(2, Constraint.availability),
    )


# --- fills when it can ---


def test_solve_fills_every_position_when_enough_staff_is_available() -> None:
    shifts = [make_shift(1, day=0, staff=2), make_shift(2, day=1, staff=2)]
    staff = employees("Noa", "Omer", "Tamar")
    given = everyone_available(shifts, staff)

    result = solve(shifts, staff, given, RULES)

    assert result.unfilled == ()
    assert {shift: len(ids) for shift, ids in staffed(result).items()} == {1: 2, 2: 2}
    assert result.score.filled == 4
    assert_hard_constraints(result, shifts, given, RULES)


# --- matrix: no solution ---


def test_solve_no_solution_reports_the_unfilled_slot_with_the_reason() -> None:
    """Product example: Tuesday needs 3, only 2 can come, Dana is excluded by minimum rest."""
    monday_night = make_shift(1, day=0, hour=23, hours=8)  # ends Tuesday 07:00
    tuesday_morning = make_shift(2, day=1, hour=7, hours=8, staff=3)
    staff = employees("Dana", "Noa", "Omer", "Tamar")
    given = answers(
        (1, 1, AVAILABLE),  # only Dana can work Monday night
        (2, 1, AVAILABLE),
        (2, 2, AVAILABLE),
        (2, 3, AVAILABLE),
    )

    result = solve([monday_night, tuesday_morning], staff, given, RULES)

    assert staffed(result) == {1: {1}, 2: {2, 3}}
    unfilled = result.unfilled[0]
    assert (unfilled.shift_id, unfilled.required, unfilled.assigned, unfilled.missing) == (
        2,
        3,
        2,
        1,
    )
    assert Exclusion(1, Constraint.min_rest, shift_id=1) in unfilled.reasons
    assert Exclusion(4, Constraint.availability) in unfilled.reasons
    assert_hard_constraints(result, [monday_night, tuesday_morning], given, RULES)


def test_solve_no_answer_counts_as_unavailable() -> None:
    staff = employees("Noa", "Omer")
    given = answers((1, 1, AVAILABLE))  # Omer never answered

    result = solve([make_shift(1, staff=2)], staff, given, RULES)

    assert staffed(result) == {1: {1}}
    assert result.unfilled[0].reasons == (Exclusion(2, Constraint.availability),)


def test_solve_proves_the_best_coverage_of_an_infeasible_week_and_says_it_is_complete() -> None:
    shifts = [make_shift(1), make_shift(2), make_shift(3)]  # three identical concurrent shifts
    staff = employees("Noa", "Omer")
    given = everyone_available(shifts, staff)

    result = solve(shifts, staff, given, RULES)

    assert result.score.filled == 2
    assert len(result.unfilled) == 1
    assert result.complete is True


# --- matrix: tight solution ---


def test_solve_tight_solution_uses_exactly_the_staff_there_is() -> None:
    """Three concurrent shifts, three employees, one perfect matching (C->3, B->2, A->1)."""
    shifts = [make_shift(1), make_shift(2), make_shift(3)]
    staff = employees("A", "B", "C")
    given = answers(
        (1, 1, AVAILABLE),
        (2, 1, AVAILABLE),
        (2, 2, AVAILABLE),
        (3, 2, AVAILABLE),
        (3, 3, AVAILABLE),
    )

    result = solve(shifts, staff, given, RULES)

    assert staffed(result) == {1: {1}, 2: {2}, 3: {3}}
    assert result.unfilled == ()


def test_solve_tight_solution_where_a_preference_competes_with_coverage() -> None:
    """A is preferred for shift 1 but is the only candidate for shift 2, and works one shift."""
    shifts = [make_shift(1, day=0), make_shift(2, day=1), make_shift(3, day=2)]
    staff = employees("A", "B", "C")
    rules = SchedulingRules(min_rest_hours=8, max_shifts_per_week=1)
    given = answers(
        (1, 1, PREFERRED),  # A is the tempting first choice for shift 1 ...
        (1, 2, AVAILABLE),
        (2, 1, AVAILABLE),  # ... but A is the only one for shift 2
        (3, 2, AVAILABLE),  # and B is the only one for shift 3
        (3, 3, AVAILABLE),
    )

    result = solve(shifts, staff, given, rules)

    assert result.unfilled == ()
    assert staffed(result)[2] == {1}
    assert_hard_constraints(result, shifts, given, rules)


# --- matrix: fairness ---


def test_solve_spreads_hours_evenly_between_two_employees() -> None:
    shifts = [make_shift(index, day=index - 1) for index in range(1, 5)]
    staff = employees("Noa", "Omer")

    result = solve(shifts, staff, everyone_available(shifts, staff), RULES)

    assert hours_by_employee(result, shifts) == {1: 16, 2: 16}


def test_solve_spreads_six_shifts_over_three_employees() -> None:
    shifts = [make_shift(index, day=index - 1) for index in range(1, 7)]
    staff = employees("Noa", "Omer", "Tamar")

    result = solve(shifts, staff, everyone_available(shifts, staff), RULES)

    assert hours_by_employee(result, shifts) == {1: 16, 2: 16, 3: 16}


def test_solve_balances_unequal_shift_lengths() -> None:
    """4 h + 4 h + 8 h: a greedy pass gives 12 h and 4 h; the balanced split is 8 h and 8 h."""
    shifts = [
        make_shift(1, day=0, hours=4),
        make_shift(2, day=1, hours=4),
        make_shift(3, day=2, hours=8),
    ]
    staff = employees("Noa", "Omer")

    result = solve(shifts, staff, everyone_available(shifts, staff), RULES)

    assert sorted(hours_by_employee(result, shifts).values()) == [8, 8]
    assert result.score.spread_minutes == 0


# --- matrix: each hard constraint in isolation ---


def test_solve_never_assigns_an_employee_who_is_unavailable() -> None:
    staff = employees("Noa", "Omer", "Tamar")
    given = answers((1, 1, UNAVAILABLE), (1, 2, AVAILABLE), (1, 3, AVAILABLE))

    result = solve([make_shift(1, staff=3)], staff, given, RULES)

    assert staffed(result) == {1: {2, 3}}
    assert result.unfilled[0].reasons == (Exclusion(1, Constraint.availability),)


def test_solve_never_exceeds_the_required_staff() -> None:
    staff = employees("Noa", "Omer", "Tamar", "Dana")
    shift = make_shift(1, staff=2)

    result = solve([shift], staff, everyone_available([shift], staff), RULES)

    assert len(staffed(result)[1]) == 2


def test_solve_never_double_books_overlapping_shifts() -> None:
    first, second = make_shift(1, hour=7, hours=8), make_shift(2, hour=10, hours=8)
    staff = employees("Noa", "Omer")
    given = answers((1, 1, AVAILABLE), (2, 1, AVAILABLE), (2, 2, AVAILABLE))

    result = solve([first, second], staff, given, RULES)

    assert staffed(result) == {1: {1}, 2: {2}}


def test_solve_never_double_books_when_only_one_employee_can_work_both() -> None:
    first, second = make_shift(1, hour=7, hours=8), make_shift(2, hour=10, hours=8)
    staff = employees("Noa")
    given = answers((1, 1, AVAILABLE), (2, 1, AVAILABLE))

    result = solve([first, second], staff, given, RULES)

    assert result.score.filled == 1
    assert result.unfilled[0].reasons == (
        Exclusion(1, Constraint.overlap, shift_id=staffed_id(result)),
    )


def staffed_id(result) -> int:
    """The id of the one shift that got staffed."""
    return next(iter(staffed(result)))


def test_solve_never_violates_the_minimum_rest() -> None:
    morning, evening = make_shift(1, hour=7, hours=8), make_shift(2, hour=15, hours=8)
    staff = employees("Noa")
    given = answers((1, 1, AVAILABLE), (2, 1, AVAILABLE))

    result = solve([morning, evening], staff, given, RULES)

    assert result.score.filled == 1
    assert result.unfilled[0].reasons[0].constraint is Constraint.min_rest


def test_solve_allows_exactly_the_minimum_rest() -> None:
    morning, night = make_shift(1, hour=7, hours=8), make_shift(2, hour=23, hours=8)  # 8 h gap
    staff = employees("Noa")
    given = answers((1, 1, AVAILABLE), (2, 1, AVAILABLE))

    result = solve([morning, night], staff, given, RULES)

    assert staffed(result) == {1: {1}, 2: {1}}


def test_solve_never_exceeds_the_max_shifts_per_week() -> None:
    shifts = [make_shift(index, day=index - 1) for index in range(1, 7)]
    staff = employees("Noa")
    given = everyone_available(shifts, staff)

    result = solve(shifts, staff, given, RULES)

    assert result.score.filled == 5
    assert len(result.unfilled) == 1
    assert result.unfilled[0].reasons == (Exclusion(1, Constraint.max_shifts),)


def test_solve_never_assigns_a_blocked_employee() -> None:
    staff = employees("Noa", "Omer")
    shift = make_shift(1)

    result = solve([shift], staff, everyone_available([shift], staff), RULES, blocks=[Block(1, 1)])

    assert staffed(result) == {1: {2}}


def test_solve_never_assigns_a_blocked_employee_who_prefers_the_shift() -> None:
    staff = employees("Noa", "Omer")
    given = answers((1, 1, PREFERRED), (1, 2, AVAILABLE))

    result = solve([make_shift(1)], staff, given, RULES, blocks=[Block(1, 1)])

    assert staffed(result) == {1: {2}}


def test_solve_reports_a_blocked_willing_employee_as_the_reason_a_slot_stays_empty() -> None:
    staff = employees("Noa", "Omer")
    given = answers((1, 1, AVAILABLE), (1, 2, UNAVAILABLE))

    result = solve([make_shift(1)], staff, given, RULES, blocks=[Block(1, 1)])

    assert result.score.filled == 0
    assert Exclusion(1, Constraint.blocked) in result.unfilled[0].reasons


def test_solve_blocks_only_the_named_shifts_of_the_employee() -> None:
    first, second = make_shift(1, day=0), make_shift(2, day=1)
    staff = employees("Noa")

    result = solve(
        [first, second],
        staff,
        everyone_available([first, second], staff),
        RULES,
        blocks=[Block(1, 1)],
    )

    assert staffed(result) == {2: {1}}


def test_solve_without_blocks_is_unchanged() -> None:
    shifts = [make_shift(1), make_shift(2, day=1)]
    staff = employees("Noa", "Omer")
    given = everyone_available(shifts, staff)

    assert solve(shifts, staff, given, RULES, blocks=[]) == solve(shifts, staff, given, RULES)


@pytest.mark.parametrize(
    "block", [Block(9, 1), Block(1, 9)], ids=["unknown_shift", "unknown_employee"]
)
def test_solve_rejects_a_block_for_an_unknown_shift_or_employee(block: Block) -> None:
    staff = employees("Noa")
    shift = make_shift(1)

    with pytest.raises(ValueError):
        solve([shift], staff, everyone_available([shift], staff), RULES, blocks=[block])


def test_solve_measures_rest_in_real_time_across_the_spring_forward_night() -> None:
    """Thu evening to Fri morning is 8 h on the wall clock but 7 h real time on 2026-03-27."""
    evening = Shift(1, *shift_bounds(date(2026, 3, 26), time(15), time(23), TZ), 1)
    morning = Shift(2, *shift_bounds(date(2026, 3, 27), time(7), time(15), TZ), 1)
    staff = employees("Noa")
    given = answers((1, 1, AVAILABLE), (2, 1, AVAILABLE))

    result = solve([evening, morning], staff, given, RULES)

    assert result.score.filled == 1
    assert result.unfilled[0].reasons[0].constraint is Constraint.min_rest


def test_solve_allows_the_same_pattern_in_a_week_without_a_clock_change() -> None:
    evening = Shift(1, *shift_bounds(date(2026, 1, 14), time(15), time(23), TZ), 1)
    morning = Shift(2, *shift_bounds(date(2026, 1, 15), time(7), time(15), TZ), 1)
    staff = employees("Noa")
    given = answers((1, 1, AVAILABLE), (2, 1, AVAILABLE))

    result = solve([evening, morning], staff, given, RULES)

    assert result.unfilled == ()


# --- matrix: preferred honored when possible ---


def test_solve_honors_a_preferred_answer_when_possible() -> None:
    staff = employees("Noa", "Omer")
    given = answers((1, 1, AVAILABLE), (1, 2, PREFERRED))

    result = solve([make_shift(1)], staff, given, RULES)

    assert staffed(result) == {1: {2}}
    assert result.score.preferred == 1


def test_solve_honors_each_employees_preferences_across_shifts() -> None:
    shifts = [make_shift(1, day=0), make_shift(2, day=1)]
    staff = employees("Noa", "Omer")
    given = answers((1, 1, PREFERRED), (1, 2, AVAILABLE), (2, 1, AVAILABLE), (2, 2, PREFERRED))

    result = solve(shifts, staff, given, RULES)

    assert staffed(result) == {1: {1}, 2: {2}}
    assert result.score.preferred == 2


def test_solve_gives_up_a_preference_rather_than_leave_a_position_unfilled() -> None:
    first, second = make_shift(1, hour=7, hours=8), make_shift(2, hour=10, hours=8)  # overlap
    staff = employees("Noa", "Omer")
    given = answers((1, 1, PREFERRED), (1, 2, AVAILABLE), (2, 1, AVAILABLE))

    result = solve([first, second], staff, given, RULES)

    assert staffed(result) == {1: {2}, 2: {1}}
    assert result.unfilled == ()


# --- score ---


def test_solve_score_counts_filled_preferred_and_spread() -> None:
    shifts = [make_shift(1, day=0), make_shift(2, day=1)]
    staff = employees("Noa", "Omer")
    given = answers((1, 1, PREFERRED), (1, 2, AVAILABLE), (2, 1, AVAILABLE), (2, 2, AVAILABLE))

    result = solve(shifts, staff, given, RULES)

    assert result.score.filled == 2
    assert result.score.preferred == 1
    assert result.score.spread_minutes == 0
    assert result.score.value == PREFERRED_WEIGHT


# --- determinism, budget, input checks ---


def test_solve_is_deterministic_and_ignores_the_order_of_its_input() -> None:
    shifts = [make_shift(index, day=index % 4, hour=7 + 8 * (index % 2)) for index in range(1, 9)]
    staff = employees("Noa", "Omer", "Tamar", "Dana")
    given = everyone_available(shifts, staff)

    first = solve(shifts, staff, given, RULES)
    again = solve(shifts, staff, given, RULES)
    shuffled = solve(shifts[::-1], staff[::-1], given[::-1], RULES)

    assert first == again
    assert shuffled.assignments == first.assignments


def test_solve_stops_at_the_step_budget_and_still_returns_a_valid_schedule() -> None:
    shifts = [make_shift(1), make_shift(2), make_shift(3)]
    staff = employees("Noa", "Omer")
    given = everyone_available(shifts, staff)
    tiny = SchedulingRules(min_rest_hours=8, max_shifts_per_week=5, max_steps=1)

    result = solve(shifts, staff, given, tiny)

    assert result.complete is False
    assert result.score.filled >= 1
    assert_hard_constraints(result, shifts, given, tiny)


@pytest.mark.parametrize(
    "build",
    [
        lambda: ([make_shift(1), make_shift(1, day=1)], employees("Noa"), []),
        lambda: ([make_shift(1)], employees("Noa") + employees("Noa"), []),
        lambda: ([make_shift(1)], employees("Noa"), answers((9, 1, AVAILABLE))),
        lambda: ([make_shift(1)], employees("Noa"), answers((1, 9, AVAILABLE))),
        lambda: (
            [make_shift(1)],
            employees("Noa"),
            [Availability(1, 1, AVAILABLE), Availability(1, 1, PREFERRED)],
        ),
    ],
    ids=[
        "duplicate_shift_id",
        "duplicate_employee_id",
        "answer_for_unknown_shift",
        "answer_for_unknown_employee",
        "two_answers_for_one_pair",
    ],
)
def test_solve_rejects_inconsistent_input(build) -> None:
    shifts, staff, given = build()

    with pytest.raises(ValueError):
        solve(shifts, staff, given, RULES)


# --- cross-check against exhaustive search ---


def random_instance(seed: int):
    rng = random.Random(seed)
    shifts = [
        make_shift(
            index,
            day=rng.randint(0, 1),
            hour=rng.choice([0, 7, 15, 23]),
            hours=rng.choice([4, 8]),
            staff=rng.randint(1, 2),
        )
        for index in range(1, rng.randint(3, 5) + 1)
    ]
    staff = employees(*[f"E{number}" for number in range(rng.randint(2, 4))])
    given = [
        Availability(shift.id, employee.id, status)
        for shift in shifts
        for employee in staff
        if (status := rng.choice([AVAILABLE, AVAILABLE, PREFERRED, UNAVAILABLE, None])) is not None
    ]
    rules = SchedulingRules(
        min_rest_hours=rng.choice([0, 4, 8]), max_shifts_per_week=rng.randint(1, 3)
    )
    return shifts, staff, given, rules


@pytest.mark.parametrize("seed", range(60))
def test_solve_fills_as_many_positions_as_exhaustive_search_and_breaks_no_rule(seed: int) -> None:
    shifts, staff, given, rules = random_instance(seed)

    result = solve(shifts, staff, given, rules)

    assert_hard_constraints(result, shifts, given, rules)
    assert result.complete is True
    assert result.score.filled == best_coverage(shifts, staff, given, rules)


@pytest.mark.parametrize("seed", range(40))
def test_solve_with_random_blocks_matches_exhaustive_search_without_those_answers(
    seed: int,
) -> None:
    shifts, staff, given, rules = random_instance(seed)
    rng = random.Random(1000 + seed)
    blocks = [
        Block(shift.id, employee.id)
        for shift in shifts
        for employee in staff
        if rng.random() < 0.25
    ]
    blocked = {(block.shift_id, block.employee_id) for block in blocks}
    open_answers = [a for a in given if (a.shift_id, a.employee_id) not in blocked]

    result = solve(shifts, staff, given, rules, blocks=blocks)

    assert_hard_constraints(result, shifts, open_answers, rules)
    assert result.score.filled == best_coverage(shifts, staff, open_answers, rules)


# --- size ---


def test_solve_handles_a_full_week_of_three_shifts_a_day() -> None:
    shifts = []
    for day in range(7):
        for number, (hour, staff_needed) in enumerate([(7, 2), (15, 2), (23, 2)]):
            shifts.append(make_shift(day * 3 + number + 1, day=day, hour=hour, staff=staff_needed))
    staff = employees(*[f"E{number}" for number in range(12)])
    rng = random.Random(5)
    given = [
        Availability(shift.id, employee.id, rng.choice([AVAILABLE, AVAILABLE, PREFERRED]))
        for shift in shifts
        for employee in staff
        if rng.random() < 0.8
    ]
    started = clock.perf_counter()

    result = solve(shifts, staff, given, RULES)

    assert clock.perf_counter() - started < 5
    assert result.unfilled == ()
    assert_hard_constraints(result, shifts, given, RULES)


def test_solve_rejects_a_problem_too_large_for_the_recursive_search() -> None:
    shift = make_shift(1, staff=501)

    with pytest.raises(ValueError):
        solve([shift], employees("Noa"), [], RULES)
