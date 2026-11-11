"""Builders for scheduler tests: shifts at readable hours, availability lists."""

from datetime import UTC, datetime, timedelta

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
