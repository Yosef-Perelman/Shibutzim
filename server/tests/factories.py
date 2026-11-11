"""Factory helpers for test data (testing-rules: factories instead of copy-pasted setup).

Every datetime is timezone-aware; nothing here reads the clock.
"""

import itertools
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.enums import AvailabilityStatus, Role, ScheduleStatus, TimeEntrySource
from app.core.security import create_access_token, hash_password
from app.core.time import shift_bounds
from app.models import (
    Assignment,
    Availability,
    Schedule,
    Shift,
    ShiftTemplate,
    TimeEntry,
    User,
)

_sequence = itertools.count(1)

DEFAULT_PASSWORD = "correct-horse-battery"
TEST_BCRYPT_ROUNDS = 4  # the minimum; production uses the default cost
NOW = datetime(2026, 3, 9, 12, 0, tzinfo=UTC)  # the frozen "current time" of API tests
BASE_CLOCK_IN = datetime(2026, 3, 9, 8, 0, tzinfo=UTC)
THIS_WEEK = date(2026, 3, 8)  # the Sunday of the week containing NOW
NEXT_WEEK = date(2026, 3, 15)


def make_user(
    session: Session,
    *,
    role: Role = Role.employee,
    email: str | None = None,
    name: str | None = None,
    hourly_rate: Decimal = Decimal("50.00"),
    is_active: bool = True,
    password: str = DEFAULT_PASSWORD,
) -> User:
    number = next(_sequence)
    user = User(
        email=email or f"user{number}@example.com",
        password_hash=hash_password(password, rounds=TEST_BCRYPT_ROUNDS),
        name=name or f"User {number}",
        role=role,
        hourly_rate=hourly_rate,
        is_active=is_active,
    )
    session.add(user)
    session.flush()
    return user


def make_time_entry(
    session: Session,
    user: User,
    *,
    clock_in: datetime = BASE_CLOCK_IN,
    duration: timedelta | None = timedelta(hours=8),
    source: TimeEntrySource = TimeEntrySource.clock,
    created_by: User | None = None,
    note: str | None = None,
) -> TimeEntry:
    """A closed entry of `duration`; pass `duration=None` for an open entry."""
    entry = TimeEntry(
        user_id=user.id,
        clock_in=clock_in,
        clock_out=None if duration is None else clock_in + duration,
        source=source,
        created_by=(created_by or user).id,
        note=note,
    )
    session.add(entry)
    session.flush()
    return entry


def auth_headers(user: User, *, now: datetime = NOW) -> dict[str, str]:
    """Authorization header with a valid token for `user`, issued at `now`."""
    token = create_access_token(user.id, user.role, now=now)
    return {"Authorization": f"Bearer {token}"}


def make_shift_template(
    session: Session,
    *,
    name: str | None = None,
    weekday: int = 1,
    start_time: time = time(7, 0),
    end_time: time = time(15, 0),
    required_staff: int = 2,
    is_active: bool = True,
) -> ShiftTemplate:
    """A template; `weekday` 0 is Sunday and the default is a Monday 07:00-15:00 shift for two."""
    number = next(_sequence)
    template = ShiftTemplate(
        name=name or f"Template {number}",
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        required_staff=required_staff,
        is_active=is_active,
    )
    session.add(template)
    session.flush()
    return template


def make_shift(
    session: Session,
    template: ShiftTemplate | None = None,
    *,
    week_start: date = NEXT_WEEK,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    required_staff: int | None = None,
) -> Shift:
    """A shift of `template` in the week starting `week_start`, snapshotting its times and staff.

    Pass `starts_at` and `ends_at` together to place it at exact instants instead.
    """
    template = template or make_shift_template(session)
    if starts_at is None or ends_at is None:
        day = week_start + timedelta(days=template.weekday)
        starts_at, ends_at = shift_bounds(
            day, template.start_time, template.end_time, get_settings().tz
        )
    shift = Shift(
        template_id=template.id,
        week_start=week_start,
        starts_at=starts_at,
        ends_at=ends_at,
        required_staff=required_staff or template.required_staff,
    )
    session.add(shift)
    session.flush()
    return shift


def make_availability(
    session: Session,
    shift: Shift,
    user: User,
    status: AvailabilityStatus = AvailabilityStatus.available,
) -> Availability:
    answer = Availability(shift_id=shift.id, user_id=user.id, status=status)
    session.add(answer)
    session.flush()
    return answer


def make_schedule(
    session: Session,
    *,
    week_start: date = NEXT_WEEK,
    status: ScheduleStatus = ScheduleStatus.draft,
    published_at: datetime | None = None,
) -> Schedule:
    """A schedule row; a `published` one gets `NOW` as its publication time unless given."""
    if status is ScheduleStatus.published and published_at is None:
        published_at = NOW
    schedule = Schedule(week_start=week_start, status=status, published_at=published_at)
    session.add(schedule)
    session.flush()
    return schedule


def make_assignment(session: Session, schedule: Schedule, shift: Shift, user: User) -> Assignment:
    assignment = Assignment(schedule_id=schedule.id, shift_id=shift.id, user_id=user.id)
    session.add(assignment)
    session.flush()
    return assignment
