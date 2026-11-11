"""Weekly shift generation from templates (architecture §6.2) and reading a week's shifts."""

from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode, Forbidden, ValidationFailed
from app.models import Shift, User
from app.repositories import shift_repository
from app.services import shift_service as service
from tests.factories import NEXT_WEEK, THIS_WEEK, make_shift, make_shift_template


def utc(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


# --- generate: contents ---


def test_generate_creates_one_shift_per_active_template(session: Session, manager: User) -> None:
    make_shift_template(session, weekday=1)
    make_shift_template(session, weekday=2)
    make_shift_template(session, weekday=3, is_active=False)

    result = service.generate_shifts(session, manager, NEXT_WEEK)

    assert result.created == 2
    assert len(result.shifts) == 2


def test_generate_places_a_shift_on_the_template_weekday_in_local_time(
    session: Session, manager: User
) -> None:
    # Monday 2026-03-16 07:00-15:00 in Asia/Jerusalem (UTC+2 in March before the 27th).
    make_shift_template(session, weekday=1, start_time=time(7, 0), end_time=time(15, 0))

    shift = service.generate_shifts(session, manager, NEXT_WEEK).shifts[0]

    assert (shift.starts_at, shift.ends_at) == (utc(3, 16, 5), utc(3, 16, 13))
    assert shift.week_start == NEXT_WEEK


def test_generate_gives_sunday_templates_the_week_start_date(
    session: Session, manager: User
) -> None:
    make_shift_template(session, weekday=0, start_time=time(7, 0), end_time=time(15, 0))

    shift = service.generate_shifts(session, manager, NEXT_WEEK).shifts[0]

    assert shift.starts_at == utc(3, 15, 5)


def test_generate_ends_a_night_shift_on_the_next_day(session: Session, manager: User) -> None:
    make_shift_template(session, weekday=1, start_time=time(23, 0), end_time=time(7, 0))

    shift = service.generate_shifts(session, manager, NEXT_WEEK).shifts[0]

    assert (shift.starts_at, shift.ends_at) == (utc(3, 16, 21), utc(3, 17, 5))


def test_generate_uses_summer_time_on_the_day_the_clocks_change(
    session: Session, manager: User
) -> None:
    # Friday 2026-03-27 07:00 is already UTC+3.
    make_shift_template(session, weekday=5, start_time=time(7, 0), end_time=time(13, 0))

    shift = service.generate_shifts(session, manager, date(2026, 3, 22)).shifts[0]

    assert (shift.starts_at, shift.ends_at) == (utc(3, 27, 4), utc(3, 27, 10))


def test_generate_snapshots_the_required_staff(session: Session, manager: User) -> None:
    template = make_shift_template(session, required_staff=3)

    shift = service.generate_shifts(session, manager, NEXT_WEEK).shifts[0]
    template.required_staff = 9

    assert shift.required_staff == 3
    assert shift.template_id == template.id


# --- generate: idempotency ---


def test_generate_twice_creates_nothing_the_second_time(session: Session, manager: User) -> None:
    make_shift_template(session, weekday=1)
    first = service.generate_shifts(session, manager, NEXT_WEEK)

    second = service.generate_shifts(session, manager, NEXT_WEEK)

    assert second.created == 0
    assert [s.id for s in second.shifts] == [s.id for s in first.shifts]


def test_generate_adds_only_the_shifts_that_are_missing(session: Session, manager: User) -> None:
    make_shift_template(session, weekday=1)
    first = service.generate_shifts(session, manager, NEXT_WEEK)
    make_shift_template(session, weekday=2)

    second = service.generate_shifts(session, manager, NEXT_WEEK)

    assert second.created == 1
    assert len(second.shifts) == 2
    assert first.shifts[0].id in [s.id for s in second.shifts]


def test_generate_keeps_the_snapshot_of_an_existing_shift(session: Session, manager: User) -> None:
    template = make_shift_template(session, required_staff=2)
    service.generate_shifts(session, manager, NEXT_WEEK)
    template.required_staff = 5

    result = service.generate_shifts(session, manager, NEXT_WEEK)

    assert result.shifts[0].required_staff == 2


def test_generate_for_one_week_does_not_touch_another(session: Session, manager: User) -> None:
    make_shift_template(session)
    service.generate_shifts(session, manager, NEXT_WEEK)

    other = service.generate_shifts(session, manager, THIS_WEEK)

    assert other.created == 1
    assert session.query(Shift).count() == 2


def test_generate_survives_a_concurrent_request_that_created_the_shift_first(
    session: Session, manager: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = make_shift_template(session)
    make_shift(session, template, week_start=NEXT_WEEK)
    real_list = shift_repository.list_for_week
    calls = []

    def stale_first_read(db: Session, week: date) -> list[Shift]:
        calls.append(week)
        return [] if len(calls) == 1 else real_list(db, week)

    monkeypatch.setattr(shift_repository, "list_for_week", stale_first_read)

    result = service.generate_shifts(session, manager, NEXT_WEEK)

    assert result.created == 0
    assert len(result.shifts) == 1


# --- generate: validation and authorization ---


@pytest.mark.parametrize("not_sunday", [date(2026, 3, 16), date(2026, 3, 21)], ids=["mon", "sat"])
def test_generate_rejects_a_week_start_that_is_not_a_sunday(
    session: Session, manager: User, not_sunday: date
) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.generate_shifts(session, manager, not_sunday)

    assert raised.value.code == ErrorCode.invalid_week_start


def test_generate_is_for_managers_only(session: Session, employee: User) -> None:
    make_shift_template(session)

    with pytest.raises(Forbidden):
        service.generate_shifts(session, employee, NEXT_WEEK)

    assert session.query(Shift).count() == 0


def test_generate_checks_authorization_before_the_week(session: Session, employee: User) -> None:
    with pytest.raises(Forbidden):
        service.generate_shifts(session, employee, date(2026, 3, 16))


def test_generate_with_no_templates_creates_nothing(session: Session, manager: User) -> None:
    result = service.generate_shifts(session, manager, NEXT_WEEK)

    assert (result.created, result.shifts) == (0, [])


# --- list ---


def test_list_returns_the_weeks_shifts_in_time_order_for_any_user(
    session: Session, employee: User
) -> None:
    late = make_shift_template(session, weekday=3)
    early = make_shift_template(session, weekday=1)
    make_shift(session, late)
    make_shift(session, early)
    make_shift(session, early, week_start=THIS_WEEK)  # another week

    found = service.list_shifts(session, employee, NEXT_WEEK)

    assert [s.template_id for s in found] == [early.id, late.id]


def test_list_exposes_the_template_name(session: Session, employee: User) -> None:
    make_shift(session, make_shift_template(session, name="Evening"))

    assert service.list_shifts(session, employee, NEXT_WEEK)[0].name == "Evening"


def test_list_rejects_a_week_start_that_is_not_a_sunday(session: Session, employee: User) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.list_shifts(session, employee, date(2026, 3, 16))

    assert raised.value.code == ErrorCode.invalid_week_start
