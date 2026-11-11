"""Builders for scheduler tests: shifts at readable hours, availability lists."""

from datetime import UTC, datetime, timedelta
from itertools import combinations

from app.core.enums import AvailabilityStatus
from app.scheduler import Availability, Employee, Shift

MONDAY = datetime(2026, 3, 9, 0, 0, tzinfo=UTC)  # any fixed instant works; the solver is zone-free
AVAILABLE = AvailabilityStatus.available
PREFERRED = AvailabilityStatus.preferred
UNAVAILABLE = AvailabilityStatus.unavailable


def make_shift(
    shift_id: int, *, day: int = 0, hour: int = 7, hours: float = 8, staff: int = 1
) -> Shift:
    """A shift starting at `hour` o'clock on day `day` after MONDAY and lasting `hours`."""
    starts_at = MONDAY + timedelta(days=day, hours=hour)
    return Shift(
        id=shift_id,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=hours),
        required_staff=staff,
    )


def employees(*names: str) -> list[Employee]:
    """Employees with ids 1..n in the order given."""
    return [Employee(id=index, name=name) for index, name in enumerate(names, start=1)]


def answers(*rows: tuple[int, int, AvailabilityStatus]) -> list[Availability]:
    """(shift_id, employee_id, status) triples as Availability objects."""
    return [Availability(shift_id=s, employee_id=e, status=status) for s, e, status in rows]


def everyone_available(shifts: list[Shift], staff: list[Employee]) -> list[Availability]:
    return [
        Availability(shift.id, employee.id, AVAILABLE) for shift in shifts for employee in staff
    ]


# --- independent checkers (deliberately not built on app.scheduler.constraints) ---

WORKABLE_STATUSES = {AVAILABLE, PREFERRED}


def status_by_pair(answers) -> dict[tuple[int, int], AvailabilityStatus]:
    return {(a.shift_id, a.employee_id): a.status for a in answers}


def fits(existing, shift, rules) -> bool:
    """Can an employee who already works `existing` also work `shift`? Plain time arithmetic."""
    if len(existing) >= rules.max_shifts_per_week:
        return False
    rest = timedelta(hours=rules.min_rest_hours)
    return all(
        shift.starts_at >= other.ends_at + rest or other.starts_at >= shift.ends_at + rest
        for other in existing
    )


def assert_hard_constraints(result, shifts, answers, rules) -> None:
    """Every hard constraint holds for `result`; fails with the first broken one."""
    by_id = {shift.id: shift for shift in shifts}
    status = status_by_pair(answers)
    per_shift: dict[int, list[int]] = {}
    per_employee: dict[int, list] = {}
    for assignment in result.assignments:
        key = (assignment.shift_id, assignment.employee_id)
        assert status.get(key) in WORKABLE_STATUSES, f"{key} was not available"
        assert assignment.employee_id not in per_shift.get(assignment.shift_id, []), f"{key} twice"
        per_shift.setdefault(assignment.shift_id, []).append(assignment.employee_id)
        per_employee.setdefault(assignment.employee_id, []).append(by_id[assignment.shift_id])
    for shift in shifts:
        assert len(per_shift.get(shift.id, [])) <= shift.required_staff, f"shift {shift.id} over"
    for employee_id, worked in per_employee.items():
        for index, shift in enumerate(worked):
            assert fits(worked[:index] + worked[index + 1 :], shift, rules), (
                f"employee {employee_id} breaks a rule on shift {shift.id}"
            )


def best_coverage(shifts, staff, answers, rules) -> int:
    """The most positions any rule-abiding schedule can fill, by exhaustive search."""
    status = status_by_pair(answers)
    candidates = {
        shift.id: [e.id for e in staff if status.get((shift.id, e.id)) in WORKABLE_STATUSES]
        for shift in shifts
    }
    best = 0
    worked: dict[int, list] = {e.id: [] for e in staff}

    def search(index: int, total: int) -> None:
        nonlocal best
        if index == len(shifts):
            best = max(best, total)
            return
        shift = shifts[index]
        for size in range(shift.required_staff + 1):
            for chosen in combinations(candidates[shift.id], size):
                if all(fits(worked[e], shift, rules) for e in chosen):
                    for e in chosen:
                        worked[e].append(shift)
                    search(index + 1, total + size)
                    for e in chosen:
                        worked[e].pop()

    search(0, 0)
    return best
