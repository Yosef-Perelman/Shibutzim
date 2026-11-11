"""Hard constraints (product-definition §6.2): the solver never violates them and manual edits are
checked with the same functions, so the rules live in one place.

Intervals are half-open: a shift ending exactly when another starts does not overlap it. Rest is
the gap between one shift's end and the next one's start and must be at least `min_rest`.
"""

from collections.abc import Iterable
from datetime import timedelta

from app.core.enums import AvailabilityStatus
from app.scheduler.rules import SchedulingRules
from app.scheduler.types import Constraint, Exclusion, Shift

WORKABLE = frozenset({AvailabilityStatus.available, AvailabilityStatus.preferred})


def is_workable(status: AvailabilityStatus | None) -> bool:
    """Only an explicit `available` or `preferred` answer lets an employee work a shift."""
    return status in WORKABLE


def overlaps(a: Shift, b: Shift) -> bool:
    return a.starts_at < b.ends_at and b.starts_at < a.ends_at


def rest_gap(a: Shift, b: Shift) -> timedelta:
    """Time from the earlier shift's end to the later one's start; negative if they overlap."""
    earlier, later = (a, b) if a.starts_at <= b.starts_at else (b, a)
    return later.starts_at - earlier.ends_at


def conflict(a: Shift, b: Shift, rules: SchedulingRules) -> Constraint | None:
    """The constraint that stops one employee from working both shifts, if any."""
    if overlaps(a, b):
        return Constraint.overlap
    if rest_gap(a, b) < rules.min_rest:
        return Constraint.min_rest
    return None


def violations(
    employee_id: int,
    shift: Shift,
    assigned: Iterable[Shift],
    status: AvailabilityStatus | None,
    rules: SchedulingRules,
) -> list[Exclusion]:
    """Every hard constraint broken by giving `shift` to an employee who already has `assigned`.

    `status` is the employee's answer for `shift` (None if they gave none). The candidate shift
    itself is ignored if it appears in `assigned`, so a caller can pass an employee's full list.
    """
    others = [other for other in assigned if other.id != shift.id]
    found: list[Exclusion] = []
    if not is_workable(status):
        found.append(Exclusion(employee_id, Constraint.availability))
    for other in others:
        broken = conflict(shift, other, rules)
        if broken is not None:
            found.append(Exclusion(employee_id, broken, shift_id=other.id))
    if len(others) >= rules.max_shifts_per_week:
        found.append(Exclusion(employee_id, Constraint.max_shifts))
    return found
