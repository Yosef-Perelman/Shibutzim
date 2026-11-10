"""Pay reports: authorization, work-day ranges and the glue to pay.calculate."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import ErrorCode, Forbidden, NotFound, ValidationFailed
from app.models import User
from app.services import pay_service
from tests.factories import make_time_entry, make_user

HOUR = timedelta(hours=1)
D = Decimal
MAR9, MAR10, MAR11 = date(2026, 3, 9), date(2026, 3, 10), date(2026, 3, 11)


def utc(day: int, hour: int) -> datetime:
    """Asia/Jerusalem is UTC+2 on these dates: 05:00 UTC is 07:00 local."""
    return datetime(2026, 3, day, hour, 0, tzinfo=UTC)


# --- one user's pay ---


def test_get_pay_of_nine_hours_applies_the_overtime_tier(session: Session, employee: User) -> None:
    # 9h at 50.00: 8 × 50.00 = 400.00, then 1 × 50.00 × 1.25 = 62.50, total 462.50
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=9 * HOUR)

    report = pay_service.get_pay(session, employee, from_day=MAR9, to_day=MAR9)

    assert report.user.id == employee.id
    assert report.breakdown.amount == D("462.50")
    assert report.breakdown.days[0].work_day == MAR9
    assert report.open_entries == 0


def test_get_pay_uses_the_employees_own_hourly_rate(session: Session) -> None:
    cheaper = make_user(session, hourly_rate=D("40.00"))
    make_time_entry(session, cheaper, clock_in=utc(9, 5), duration=8 * HOUR)

    report = pay_service.get_pay(session, cheaper, from_day=MAR9, to_day=MAR9)

    assert report.breakdown.amount == D("320.00")  # 8 × 40.00


def test_get_pay_sums_a_split_shift_before_the_tiers(session: Session, employee: User) -> None:
    # 07:00-11:00 and 16:00-22:00 local = 4h + 6h = 10h: 8 × 50.00 + 2 × 62.50 = 525.00
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=4 * HOUR)
    make_time_entry(session, employee, clock_in=utc(9, 14), duration=6 * HOUR)

    report = pay_service.get_pay(session, employee, from_day=MAR9, to_day=MAR9)

    assert len(report.breakdown.days) == 1
    assert report.breakdown.amount == D("525.00")


def test_get_pay_range_is_by_local_work_day_and_inclusive(session: Session, employee: User) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=8 * HOUR)  # Mar 9 07:00 local
    make_time_entry(session, employee, clock_in=utc(10, 5), duration=8 * HOUR)  # Mar 10
    make_time_entry(session, employee, clock_in=utc(11, 5), duration=8 * HOUR)  # Mar 11

    report = pay_service.get_pay(session, employee, from_day=MAR9, to_day=MAR10)

    assert [day.work_day for day in report.breakdown.days] == [MAR9, MAR10]
    assert report.breakdown.amount == D("800.00")


def test_get_pay_counts_a_midnight_crossing_entry_on_its_start_day(
    session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 20), duration=8 * HOUR)  # 22:00 -> 06:00

    on_start_day = pay_service.get_pay(session, employee, from_day=MAR9, to_day=MAR9)
    on_next_day = pay_service.get_pay(session, employee, from_day=MAR10, to_day=MAR10)

    assert on_start_day.breakdown.amount == D("400.00")
    assert on_next_day.breakdown.amount == D("0.00")


def test_get_pay_excludes_open_entries_and_reports_their_count(
    session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=8 * HOUR)
    make_time_entry(session, employee, clock_in=utc(10, 5), duration=None)

    report = pay_service.get_pay(session, employee, from_day=MAR9, to_day=MAR10)

    assert report.breakdown.amount == D("400.00")
    assert report.open_entries == 1


def test_get_pay_with_no_entries_is_zero(session: Session, employee: User) -> None:
    report = pay_service.get_pay(session, employee, from_day=MAR9, to_day=MAR10)

    assert report.breakdown.days == ()
    assert report.breakdown.amount == D("0.00")


def test_get_pay_ignores_other_employees_entries(
    session: Session, employee: User, other_employee: User
) -> None:
    make_time_entry(session, other_employee, clock_in=utc(9, 5), duration=8 * HOUR)

    report = pay_service.get_pay(session, employee, from_day=MAR9, to_day=MAR9)

    assert report.breakdown.amount == D("0.00")


def test_get_pay_defaults_to_the_current_user(session: Session, employee: User) -> None:
    report = pay_service.get_pay(session, employee, user_id=None, from_day=MAR9, to_day=MAR9)

    assert report.user.id == employee.id


def test_get_pay_lets_a_manager_read_anyone(
    session: Session, manager: User, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=8 * HOUR)

    report = pay_service.get_pay(session, manager, user_id=employee.id, from_day=MAR9, to_day=MAR9)

    assert (report.user.id, report.breakdown.amount) == (employee.id, D("400.00"))


def test_get_pay_of_someone_else_is_forbidden_for_an_employee(
    session: Session, employee: User, other_employee: User
) -> None:
    with pytest.raises(Forbidden) as raised:
        pay_service.get_pay(
            session, employee, user_id=other_employee.id, from_day=MAR9, to_day=MAR9
        )

    assert raised.value.code == ErrorCode.forbidden


def test_get_pay_does_not_reveal_whether_a_user_exists_to_an_employee(
    session: Session, employee: User
) -> None:
    with pytest.raises(Forbidden):
        pay_service.get_pay(session, employee, user_id=999_999, from_day=MAR9, to_day=MAR9)


def test_get_pay_of_an_unknown_user_is_user_not_found_for_a_manager(
    session: Session, manager: User
) -> None:
    with pytest.raises(NotFound) as raised:
        pay_service.get_pay(session, manager, user_id=999_999, from_day=MAR9, to_day=MAR9)

    assert raised.value.code == ErrorCode.user_not_found


def test_get_pay_with_from_after_to_is_a_validation_error(session: Session, employee: User) -> None:
    with pytest.raises(ValidationFailed) as raised:
        pay_service.get_pay(session, employee, from_day=MAR10, to_day=MAR9)

    assert raised.value.code == ErrorCode.validation_error


# --- team pay (manager) ---


def test_get_team_pay_is_forbidden_for_an_employee(session: Session, employee: User) -> None:
    with pytest.raises(Forbidden):
        pay_service.get_team_pay(session, employee, from_day=MAR9, to_day=MAR9)


def test_get_team_pay_lists_every_active_user_with_their_own_pay(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=8 * HOUR)  # 400.00
    make_time_entry(session, other_employee, clock_in=utc(9, 5), duration=9 * HOUR)  # 462.50

    team = pay_service.get_team_pay(session, manager, from_day=MAR9, to_day=MAR9)

    amounts = {row.user.name: row.breakdown.amount for row in team}
    assert amounts == {
        "Dana Other": D("462.50"),
        "Eli Employee": D("400.00"),
        "Mia Manager": D("0.00"),
    }


def test_get_team_pay_is_ordered_by_name(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    team = pay_service.get_team_pay(session, manager, from_day=MAR9, to_day=MAR9)

    assert [row.user.name for row in team] == ["Dana Other", "Eli Employee", "Mia Manager"]


def test_get_team_pay_includes_an_inactive_user_only_if_they_worked_in_the_period(
    session: Session, manager: User
) -> None:
    worked = make_user(session, name="Worked Before", is_active=False)
    idle = make_user(session, name="Never Worked", is_active=False)
    make_time_entry(session, worked, clock_in=utc(9, 5), duration=8 * HOUR)

    team = pay_service.get_team_pay(session, manager, from_day=MAR9, to_day=MAR9)

    names = [row.user.name for row in team]
    assert "Worked Before" in names
    assert idle.name not in names


def test_get_team_pay_reports_open_entries_per_user(
    session: Session, manager: User, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=None)

    team = pay_service.get_team_pay(session, manager, from_day=MAR9, to_day=MAR9)

    row = next(row for row in team if row.user.id == employee.id)
    assert (row.open_entries, row.breakdown.amount) == (1, D("0.00"))


def test_get_team_pay_with_from_after_to_is_a_validation_error(
    session: Session, manager: User
) -> None:
    with pytest.raises(ValidationFailed):
        pay_service.get_team_pay(session, manager, from_day=MAR10, to_day=MAR9)


def test_get_team_pay_includes_managers_who_clock_hours(session: Session) -> None:
    working_manager = make_user(session, role=Role.manager, name="Working Manager")
    make_time_entry(session, working_manager, clock_in=utc(9, 5), duration=8 * HOUR)

    team = pay_service.get_team_pay(session, working_manager, from_day=MAR9, to_day=MAR9)

    assert team[0].breakdown.amount == D("400.00")
