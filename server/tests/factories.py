"""Factory helpers for test data (testing-rules: factories instead of copy-pasted setup).

Every datetime is timezone-aware; nothing here reads the clock.
"""

import itertools
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.enums import Role, TimeEntrySource
from app.models import TimeEntry, User

_sequence = itertools.count(1)

DEFAULT_PASSWORD = "correct-horse-battery"
BASE_CLOCK_IN = datetime(2026, 3, 9, 8, 0, tzinfo=UTC)


def make_user(
    session: Session,
    *,
    role: Role = Role.employee,
    email: str | None = None,
    name: str | None = None,
    hourly_rate: Decimal = Decimal("50.00"),
    is_active: bool = True,
    password_hash: str = "not-a-real-hash",
) -> User:
    number = next(_sequence)
    user = User(
        email=email or f"user{number}@example.com",
        password_hash=password_hash,
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
