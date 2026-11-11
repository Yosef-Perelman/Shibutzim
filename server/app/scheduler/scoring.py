"""Soft constraints (product-definition §6.2): honor `preferred` answers, spread hours fairly.

The objective is lexicographic: fill as many positions as possible first, then maximize
`value = preferred * PREFERRED_WEIGHT - spread_minutes`. The weight is a named constant, not a
rule, because v1 has no UI to edit it and tests need fixed values.
"""

from collections.abc import Iterable, Mapping

from app.core.enums import AvailabilityStatus
from app.scheduler.types import Score, Shift

PREFERRED_WEIGHT = 120  # minutes of hours spread one honored preference is worth (two hours)
SECONDS_PER_MINUTE = 60


def shift_minutes(shift: Shift) -> int:
    return int(shift.duration.total_seconds() // SECONDS_PER_MINUTE)


def score(
    pairs: Iterable[tuple[int, int]],
    shifts: Mapping[int, Shift],
    status: Mapping[tuple[int, int], AvailabilityStatus],
    participants: Iterable[int],
) -> Score:
    """Score (shift_id, employee_id) pairs.

    `participants` are the employees who answered at all; the spread is the gap between the
    most and the least hours among them, so someone who asked for shifts and got none counts.
    """
    minutes = {employee: 0 for employee in participants}
    filled = preferred = 0
    for shift_id, employee_id in pairs:
        filled += 1
        if status.get((shift_id, employee_id)) is AvailabilityStatus.preferred:
            preferred += 1
        minutes[employee_id] = minutes.get(employee_id, 0) + shift_minutes(shifts[shift_id])
    spread = max(minutes.values()) - min(minutes.values()) if minutes else 0
    return Score(
        filled=filled,
        preferred=preferred,
        spread_minutes=spread,
        value=preferred * PREFERRED_WEIGHT - spread,
    )
