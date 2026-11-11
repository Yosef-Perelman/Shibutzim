"""The solver: backtracking search with forward checking, then a hill-climbing polish.

Phase 1 (coverage). Depth-first search over the shifts that still need staff. At each node it
picks the most constrained shift (fewest candidates beyond what it needs), tries its candidates
best-first (preferred, then fewest hours so far) and, after each placement, removes the employee
from every shift they can no longer work (overlap, minimum rest, max shifts per week). A shift
whose candidates run out stays partly unfilled, so a complete assignment always exists and the
search is branch and bound on the number of filled positions. It stops at the first assignment
that reaches the optimistic bound (nothing more can be filled) or when `max_steps` search nodes
are used; the first dive always finishes, so there is always a valid result.

Phase 2 (soft constraints). Replace one employee on one assignment while that strictly improves
the score of `scoring.py`, within the remaining budget.

Everything is ordered by explicit keys (ids, start times), so equal input gives equal output
whatever the order of the lists passed in. A `Block` removes one employee from one shift before the
search starts, like an unavailable answer, but is reported as its own reason. The module is pure:
no I/O, no clock.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.core.enums import AvailabilityStatus
from app.scheduler import scoring
from app.scheduler.constraints import conflict, is_workable, violations
from app.scheduler.rules import SchedulingRules
from app.scheduler.types import (
    Assignment,
    Availability,
    Block,
    Constraint,
    Employee,
    Exclusion,
    ScheduleResult,
    Score,
    Shift,
    TraceEvent,
    TraceKind,
    UnfilledSlot,
)

MAX_POSITIONS = 500  # the search recurses once per placement; stay well below Python's limit
MAX_TRACE_EVENTS = 20_000


@dataclass(frozen=True)
class Problem:
    """Validated, indexed input. Shifts are in (start, id) order, employees in id order."""

    rules: SchedulingRules
    shifts: tuple[Shift, ...]
    shift_by_id: dict[int, Shift]
    employee_ids: tuple[int, ...]
    status: dict[tuple[int, int], AvailabilityStatus]
    candidates: dict[int, frozenset[int]]  # employees who answered available or preferred
    conflicts: dict[int, dict[int, Constraint]]  # shift -> shifts one employee cannot combine
    participants: frozenset[int]  # employees who answered available or preferred at least once
    blocked: frozenset[tuple[int, int]]  # (shift id, employee id) pairs ruled out by the manager


def build_problem(
    shifts: Iterable[Shift],
    employees: Iterable[Employee],
    availabilities: Iterable[Availability],
    rules: SchedulingRules,
    blocks: Iterable[Block] = (),
) -> Problem:
    ordered = tuple(sorted(shifts, key=lambda shift: (shift.starts_at, shift.id)))
    shift_by_id = {shift.id: shift for shift in ordered}
    employee_ids = tuple(sorted(employee.id for employee in employees))
    if len(shift_by_id) != len(ordered):
        raise ValueError("shift ids must be unique")
    if len(set(employee_ids)) != len(employee_ids):
        raise ValueError("employee ids must be unique")
    if sum(shift.required_staff for shift in ordered) > MAX_POSITIONS:
        raise ValueError(f"more than {MAX_POSITIONS} positions is too large for this solver")

    status: dict[tuple[int, int], AvailabilityStatus] = {}
    for answer in availabilities:
        key = (answer.shift_id, answer.employee_id)
        if answer.shift_id not in shift_by_id or answer.employee_id not in employee_ids:
            raise ValueError(f"availability {key} names an unknown shift or employee")
        if key in status:
            raise ValueError(f"two availability answers for {key}")
        status[key] = answer.status

    blocked = frozenset((block.shift_id, block.employee_id) for block in blocks)
    for shift_id, employee_id in blocked:
        if shift_id not in shift_by_id or employee_id not in employee_ids:
            raise ValueError(f"block {(shift_id, employee_id)} names an unknown shift or employee")

    candidates = {
        shift.id: frozenset(
            e
            for e in employee_ids
            if is_workable(status.get((shift.id, e))) and (shift.id, e) not in blocked
        )
        for shift in ordered
    }
    return Problem(
        rules=rules,
        shifts=ordered,
        shift_by_id=shift_by_id,
        employee_ids=employee_ids,
        status=status,
        candidates=candidates,
        conflicts=find_conflicts(ordered, rules),
        participants=frozenset(e for found in candidates.values() for e in found),
        blocked=blocked,
    )


def find_conflicts(
    shifts: Sequence[Shift], rules: SchedulingRules
) -> dict[int, dict[int, Constraint]]:
    found: dict[int, dict[int, Constraint]] = {shift.id: {} for shift in shifts}
    for index, first in enumerate(shifts):
        for second in shifts[index + 1 :]:
            broken = conflict(first, second, rules)
            if broken is not None:
                found[first.id][second.id] = broken
                found[second.id][first.id] = broken
    return found


class Search:
    """Phase 1: depth-first branch and bound on the number of filled positions."""

    def __init__(self, problem: Problem, *, trace: bool) -> None:
        self.problem = problem
        self.domains = {shift_id: set(found) for shift_id, found in problem.candidates.items()}
        self.need = {shift.id: shift.required_staff for shift in problem.shifts}
        self.worked: dict[int, list[int]] = {e: [] for e in problem.employee_ids}
        self.minutes = {e: 0 for e in problem.employee_ids}
        self.chosen: list[tuple[int, int]] = []
        self.trail: list[tuple[int, int]] = []  # domain removals, undone on backtrack
        self.best: list[tuple[int, int]] | None = None
        self.best_filled = -1
        self.steps = 0
        self.exhausted = False
        self.done = False
        self.tracing = trace
        self.events: list[TraceEvent] = []
        self.truncated = False
        if trace:
            self.trace_initial_exclusions()
        self.target = self.bound()

    # --- running ---

    def run(self) -> None:
        self.search()

    def search(self) -> None:
        self.steps += 1
        if self.best is not None:
            if self.steps > self.problem.rules.max_steps:
                self.exhausted = True
                return
            if self.bound() <= self.best_filled:
                return
        shift_id = self.pick_shift()
        if shift_id is None:
            self.record_leaf()
            return
        node_mark = len(self.trail)
        for employee in self.ordered_candidates(shift_id):
            mark = len(self.trail)
            self.assign(employee, shift_id)
            self.search()
            self.undo(mark)
            self.unassign(employee, shift_id)
            if self.exhausted or self.done:
                break
            self.remove(shift_id, employee)  # the rest of this node excludes the one just tried
            if self.best is not None and self.bound() <= self.best_filled:
                break
        self.undo(node_mark)

    def record_leaf(self) -> None:
        filled = len(self.chosen)
        if filled > self.best_filled:
            self.best, self.best_filled = list(self.chosen), filled
            self.done = filled >= self.target

    # --- choosing ---

    def bound(self) -> int:
        """An optimistic count of positions that can still end up filled."""
        placed = len(self.chosen)
        by_candidates = sum(
            min(need, len(self.domains[shift_id])) for shift_id, need in self.need.items() if need
        )
        by_capacity = sum(
            max(self.problem.rules.max_shifts_per_week - len(worked), 0)
            for worked in self.worked.values()
        )
        return placed + min(by_candidates, by_capacity)

    def pick_shift(self) -> int | None:
        """The unfilled shift with the fewest candidates beyond what it needs; ties by time."""
        picked: int | None = None
        picked_slack = 0
        for shift in self.problem.shifts:
            candidates = len(self.domains[shift.id])
            if self.need[shift.id] == 0 or candidates == 0:
                continue
            slack = candidates - self.need[shift.id]
            if picked is None or slack < picked_slack:
                picked, picked_slack = shift.id, slack
        return picked

    def ordered_candidates(self, shift_id: int) -> list[int]:
        status = self.problem.status
        return sorted(
            self.domains[shift_id],
            key=lambda e: (
                status[(shift_id, e)] is not AvailabilityStatus.preferred,
                self.minutes[e],
                e,
            ),
        )

    # --- changing and undoing the state ---

    def assign(self, employee: int, shift_id: int) -> None:
        self.chosen.append((shift_id, employee))
        self.need[shift_id] -= 1
        self.worked[employee].append(shift_id)
        self.minutes[employee] += scoring.shift_minutes(self.problem.shift_by_id[shift_id])
        self.emit(TraceEvent(TraceKind.assign, shift_id, employee))
        self.remove(shift_id, employee)  # an employee works a shift once
        for other, broken in self.problem.conflicts[shift_id].items():
            if employee in self.domains[other]:
                self.remove(other, employee, broken, because=shift_id)
        if len(self.worked[employee]) >= self.problem.rules.max_shifts_per_week:
            for other, domain in self.domains.items():
                if employee in domain:
                    self.remove(other, employee, Constraint.max_shifts)

    def unassign(self, employee: int, shift_id: int) -> None:
        self.chosen.pop()
        self.need[shift_id] += 1
        self.worked[employee].pop()
        self.minutes[employee] -= scoring.shift_minutes(self.problem.shift_by_id[shift_id])
        self.emit(TraceEvent(TraceKind.backtrack, shift_id, employee))

    def remove(
        self,
        shift_id: int,
        employee: int,
        broken: Constraint | None = None,
        *,
        because: int | None = None,
    ) -> None:
        self.domains[shift_id].discard(employee)
        self.trail.append((shift_id, employee))
        if broken is not None:
            self.emit(TraceEvent(TraceKind.exclude, shift_id, employee, broken, because))

    def undo(self, mark: int) -> None:
        while len(self.trail) > mark:
            shift_id, employee = self.trail.pop()
            self.domains[shift_id].add(employee)

    # --- trace ---

    def emit(self, event: TraceEvent) -> None:
        if not self.tracing:
            return
        if len(self.events) >= MAX_TRACE_EVENTS:
            self.truncated = True
            return
        self.events.append(event)

    def trace_initial_exclusions(self) -> None:
        for shift in self.problem.shifts:
            for employee in self.problem.employee_ids:
                if employee not in self.problem.candidates[shift.id]:
                    blocked = (shift.id, employee) in self.problem.blocked
                    reason = Constraint.blocked if blocked else Constraint.availability
                    self.emit(TraceEvent(TraceKind.exclude, shift.id, employee, reason))


def improve(
    problem: Problem, pairs: list[tuple[int, int]], budget: int
) -> tuple[list[tuple[int, int]], int]:
    """Phase 2: swap one employee on one assignment while the score strictly improves.

    Returns the improved pairs and the number of candidate moves examined (at most `budget`
    plus the moves of one pass).
    """
    current = list(pairs)
    best = score_of(problem, current)
    examined = 0
    improved = True
    while improved and examined < budget:
        improved = False
        worked = shifts_by_employee(problem, current)
        for index, (shift_id, _) in enumerate(current):
            shift = problem.shift_by_id[shift_id]
            taken = {employee for sid, employee in current if sid == shift_id}
            for candidate in sorted(problem.candidates[shift_id] - taken):
                examined += 1
                status = problem.status.get((shift_id, candidate))
                if violations(candidate, shift, worked[candidate], status, problem.rules):
                    continue
                trial = [*current[:index], (shift_id, candidate), *current[index + 1 :]]
                trial_score = score_of(problem, trial)
                if trial_score.key > best.key:
                    current, best, improved = trial, trial_score, True
                    break
            if improved or examined >= budget:
                break
    return current, examined


def score_of(problem: Problem, pairs: list[tuple[int, int]]) -> Score:
    return scoring.score(pairs, problem.shift_by_id, problem.status, problem.participants)


def shifts_by_employee(
    problem: Problem, pairs: Iterable[tuple[int, int]]
) -> dict[int, list[Shift]]:
    worked: dict[int, list[Shift]] = defaultdict(list)
    for shift_id, employee in pairs:
        worked[employee].append(problem.shift_by_id[shift_id])
    return worked


def find_unfilled(problem: Problem, pairs: list[tuple[int, int]]) -> tuple[UnfilledSlot, ...]:
    """Shifts short of staff, each with why every employee not on it could not take it."""
    on_shift: dict[int, set[int]] = defaultdict(set)
    for shift_id, employee in pairs:
        on_shift[shift_id].add(employee)
    worked = shifts_by_employee(problem, pairs)
    unfilled = []
    for shift in problem.shifts:
        have = on_shift[shift.id]
        if len(have) >= shift.required_staff:
            continue
        reasons: list[Exclusion] = []
        for employee in problem.employee_ids:
            if employee not in have:
                status = problem.status.get((shift.id, employee))
                blocked = (shift.id, employee) in problem.blocked
                reasons.extend(
                    violations(
                        employee, shift, worked[employee], status, problem.rules, blocked=blocked
                    )
                )
        unfilled.append(UnfilledSlot(shift.id, shift.required_staff, len(have), tuple(reasons)))
    return tuple(unfilled)


def solve(
    shifts: Iterable[Shift],
    employees: Iterable[Employee],
    availabilities: Iterable[Availability],
    rules: SchedulingRules,
    *,
    blocks: Iterable[Block] = (),
    trace: bool = False,
) -> ScheduleResult:
    """Build the best schedule found for one week; see the module docstring for the method.

    Raises `ValueError` for inconsistent input (duplicate ids, answers or blocks for unknown
    shifts or employees, two answers for one pair) or a problem above `MAX_POSITIONS`.
    """
    problem = build_problem(shifts, employees, availabilities, rules, blocks)
    search = Search(problem, trace=trace)
    search.run()
    pairs = search.best or []

    pairs, examined = improve(problem, pairs, max(rules.max_steps - search.steps, 0))
    order = {shift.id: index for index, shift in enumerate(problem.shifts)}
    pairs.sort(key=lambda pair: (order[pair[0]], pair[1]))
    return ScheduleResult(
        assignments=tuple(Assignment(shift_id, employee) for shift_id, employee in pairs),
        score=score_of(problem, pairs),
        unfilled=find_unfilled(problem, pairs),
        steps=search.steps + examined,
        complete=not search.exhausted,
        trace=tuple(search.events),
        trace_truncated=search.truncated,
    )
