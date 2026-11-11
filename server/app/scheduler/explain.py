"""Plain-language reasons for unfilled slots (product-definition §5.2).

"Tuesday 07:00 needs 3, only 2 available; Dana excluded by minimum rest": the shift's local
weekday and start, how many are required and placed, then each employee who said they could work
the shift but was excluded by a hard constraint. Employees who did not answer `available` are
not listed, whatever else applies to them: they were never candidates.
"""

from collections.abc import Iterable
from zoneinfo import ZoneInfo

from app.core.time import weekday_sunday_based
from app.scheduler.types import Constraint, Employee, Exclusion, ScheduleResult, Shift

WEEKDAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
CONSTRAINT_PHRASES = {
    Constraint.overlap: "overlap",
    Constraint.min_rest: "minimum rest",
    Constraint.max_shifts: "max shifts per week",
}


def describe_shift(shift: Shift, tz: ZoneInfo) -> str:
    """The local weekday and start time, e.g. "Tuesday 07:00"."""
    local = shift.starts_at.astimezone(tz)
    return f"{WEEKDAY_NAMES[weekday_sunday_based(local.date())]} {local:%H:%M}"


def explain(
    result: ScheduleResult, shifts: Iterable[Shift], employees: Iterable[Employee], tz: ZoneInfo
) -> list[str]:
    """One sentence per unfilled slot, in the order of `result.unfilled`."""
    shift_by_id = {shift.id: shift for shift in shifts}
    names = {employee.id: employee.name for employee in employees}
    sentences = []
    for slot in result.unfilled:
        sentence = (
            f"{describe_shift(shift_by_id[slot.shift_id], tz)} needs {slot.required}, "
            f"only {slot.assigned} available"
        )
        for employee_id, phrases in excluded_by(slot.reasons).items():
            sentence += f"; {names[employee_id]} excluded by {' and '.join(phrases)}"
        sentences.append(sentence)
    return sentences


def excluded_by(reasons: Iterable[Exclusion]) -> dict[int, list[str]]:
    """employee id -> phrases of the hard constraints that blocked a willing employee, in id order.

    Someone who did not answer `available` was never a candidate, so no other rule is blamed for
    their absence even if one also applies.
    """
    reasons = list(reasons)
    unwilling = {r.employee_id for r in reasons if r.constraint is Constraint.availability}
    found: dict[int, list[str]] = {}
    for reason in reasons:
        if reason.employee_id in unwilling:
            continue
        phrases = found.setdefault(reason.employee_id, [])
        phrase = CONSTRAINT_PHRASES[reason.constraint]
        if phrase not in phrases:  # two conflicting shifts read as one reason
            phrases.append(phrase)
    return dict(sorted(found.items()))
