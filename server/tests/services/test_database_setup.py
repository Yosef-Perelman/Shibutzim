"""The test database behaves like production: constraints hold and tests do not leak."""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models import TimeEntry, User
from tests.factories import BASE_CLOCK_IN, make_time_entry, make_user


def test_committed_data_is_invisible_outside_the_test_transaction(
    session: Session, engine: Engine
) -> None:
    make_user(session, email="isolated@example.com")
    session.commit()  # services commit; the outer transaction still rolls it back

    with engine.connect() as other_connection:
        visible = other_connection.execute(
            text("SELECT count(*) FROM users WHERE email = 'isolated@example.com'")
        ).scalar_one()

    assert visible == 0


def test_each_test_starts_with_an_empty_users_table(session: Session) -> None:
    assert session.scalar(select(func.count()).select_from(User)) == 0


def test_user_email_is_unique(session: Session) -> None:
    make_user(session, email="same@example.com")

    with pytest.raises(IntegrityError):
        make_user(session, email="same@example.com")


def test_user_money_round_trips_as_decimal(session: Session) -> None:
    user = make_user(session, hourly_rate=Decimal("41.50"))
    session.expire(user)

    assert user.hourly_rate == Decimal("41.50")
    assert isinstance(user.hourly_rate, Decimal)


def test_timestamps_round_trip_timezone_aware(session: Session, employee: User) -> None:
    entry = make_time_entry(session, employee)
    session.expire(entry)

    assert entry.clock_in == BASE_CLOCK_IN
    assert entry.clock_in.tzinfo is not None


def test_an_employee_cannot_have_two_open_entries(session: Session, employee: User) -> None:
    make_time_entry(session, employee, duration=None)

    with pytest.raises(IntegrityError):
        make_time_entry(
            session, employee, duration=None, clock_in=BASE_CLOCK_IN + timedelta(days=1)
        )


def test_open_entries_of_different_employees_are_allowed(
    session: Session, employee: User, other_employee: User
) -> None:
    make_time_entry(session, employee, duration=None)
    make_time_entry(session, other_employee, duration=None)

    open_entries = session.scalar(
        select(func.count()).select_from(TimeEntry).where(TimeEntry.clock_out.is_(None))
    )
    assert open_entries == 2


def test_clock_out_must_be_after_clock_in(session: Session, employee: User) -> None:
    with pytest.raises(IntegrityError):
        make_time_entry(session, employee, duration=timedelta(0))


def test_role_is_restricted_to_known_values(session: Session) -> None:
    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO users (email, password_hash, name, role, hourly_rate) "
                "VALUES ('x@example.com', 'h', 'X', 'admin', 10)"
            )
        )


def test_factories_create_the_expected_roles(manager: User, employee: User) -> None:
    assert manager.role is Role.manager
    assert employee.role is Role.employee
