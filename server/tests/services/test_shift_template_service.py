"""Shift-template business rules and authorization (product-definition §6.2, architecture §5)."""

from datetime import time

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode, Forbidden, NotFound
from app.models import ShiftTemplate, User
from app.services import shift_template_service as service
from tests.factories import make_shift, make_shift_template

NEW_TEMPLATE = {
    "name": "Morning",
    "weekday": 0,
    "start_time": time(7, 0),
    "end_time": time(15, 0),
    "required_staff": 2,
}


# --- authorization ---


def test_every_operation_is_for_managers_only(session: Session, employee: User) -> None:
    template = make_shift_template(session)

    with pytest.raises(Forbidden):
        service.list_shift_templates(session, employee)
    with pytest.raises(Forbidden):
        service.create_shift_template(session, employee, **NEW_TEMPLATE)
    with pytest.raises(Forbidden):
        service.update_shift_template(session, employee, template.id, changes={"name": "x"})


def test_an_employee_is_forbidden_even_for_a_template_that_does_not_exist(
    session: Session, employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.update_shift_template(session, employee, 999_999, changes={"name": "x"})


def test_a_forbidden_create_writes_nothing(session: Session, employee: User) -> None:
    with pytest.raises(Forbidden):
        service.create_shift_template(session, employee, **NEW_TEMPLATE)

    assert session.query(ShiftTemplate).count() == 0


# --- list ---


def test_list_orders_templates_by_weekday_then_start_time(session: Session, manager: User) -> None:
    evening = make_shift_template(session, weekday=1, start_time=time(15, 0), end_time=time(23, 0))
    morning = make_shift_template(session, weekday=1, start_time=time(7, 0))
    sunday = make_shift_template(session, weekday=0, start_time=time(23, 0), end_time=time(7, 0))

    found = service.list_shift_templates(session, manager)

    assert [t.id for t in found] == [sunday.id, morning.id, evening.id]


def test_list_can_hide_deactivated_templates(session: Session, manager: User) -> None:
    active = make_shift_template(session)
    make_shift_template(session, is_active=False)

    found = service.list_shift_templates(session, manager, active_only=True)

    assert [t.id for t in found] == [active.id]


def test_list_shows_deactivated_templates_by_default(session: Session, manager: User) -> None:
    make_shift_template(session, is_active=False)

    assert len(service.list_shift_templates(session, manager)) == 1


# --- create ---


def test_create_stores_an_active_template(session: Session, manager: User) -> None:
    template = service.create_shift_template(session, manager, **NEW_TEMPLATE)

    stored = session.get(ShiftTemplate, template.id)
    assert (stored.name, stored.weekday, stored.start_time, stored.end_time) == (
        "Morning",
        0,
        time(7, 0),
        time(15, 0),
    )
    assert stored.required_staff == 2
    assert stored.is_active is True


def test_create_allows_an_end_time_before_the_start_time_for_a_night_shift(
    session: Session, manager: User
) -> None:
    template = service.create_shift_template(
        session, manager, **{**NEW_TEMPLATE, "start_time": time(23, 0), "end_time": time(7, 0)}
    )

    assert (template.start_time, template.end_time) == (time(23, 0), time(7, 0))


# --- update ---


def test_update_changes_only_the_given_fields(session: Session, manager: User) -> None:
    template = make_shift_template(session, name="Old", required_staff=2, weekday=1)

    updated = service.update_shift_template(
        session, manager, template.id, changes={"name": "New", "required_staff": 3}
    )

    assert (updated.name, updated.required_staff, updated.weekday) == ("New", 3, 1)


def test_update_deactivates_a_template_without_deleting_it(session: Session, manager: User) -> None:
    template = make_shift_template(session)

    service.update_shift_template(session, manager, template.id, changes={"is_active": False})

    assert session.get(ShiftTemplate, template.id).is_active is False


def test_update_does_not_rewrite_shifts_already_generated(session: Session, manager: User) -> None:
    template = make_shift_template(session, required_staff=2, start_time=time(7, 0))
    shift = make_shift(session, template)
    original = (shift.starts_at, shift.ends_at, shift.required_staff)

    service.update_shift_template(
        session, manager, template.id, changes={"required_staff": 5, "start_time": time(9, 0)}
    )

    assert (shift.starts_at, shift.ends_at, shift.required_staff) == original


def test_update_of_a_missing_template_is_not_found(session: Session, manager: User) -> None:
    with pytest.raises(NotFound) as raised:
        service.update_shift_template(session, manager, 999_999, changes={"name": "x"})

    assert raised.value.code == ErrorCode.shift_template_not_found
