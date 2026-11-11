"""Manual edits of a schedule: overlap and minimum rest block, everything else warns
(product-definition §5.2)."""

from datetime import date, time

import pytest
from sqlalchemy.orm import Session

from app.core.enums import AvailabilityStatus, Role, ScheduleStatus
from app.core.errors import Conflict, ErrorCode, Forbidden, NotFound, ValidationFailed
from app.models import Assignment, Schedule, Shift, User
from app.services import assignment_service as service
from tests.factories import (
    NEXT_WEEK,
    THIS_WEEK,
    make_assignment,
    make_availability,
    make_schedule,
    make_shift,
    make_shift_template,
    make_user,
)

AVAILABLE = AvailabilityStatus.available
PREFERRED = AvailabilityStatus.preferred
UNAVAILABLE = AvailabilityStatus.unavailable


def shift_at(
    session: Session,
    *,
    weekday: int = 1,
    start: int = 7,
    hours: int = 8,
    staff: int = 2,
    week: date = NEXT_WEEK,
) -> Shift:
    template = make_shift_template(
        session,
        weekday=weekday,
        start_time=time(start % 24, 0),
        end_time=time((start + hours) % 24, 0),
        required_staff=staff,
    )
    return make_shift(session, template, week_start=week)


def codes(edit) -> list[str]:
    return [warning.code for warning in edit.warnings]


def count(session: Session) -> int:
    return session.query(Assignment).count()


# --- add: the happy path ---


def test_add_assigns_an_available_employee_without_warnings(
    session: Session, manager: User, employee: User
) -> None:
    schedule, shift = make_schedule(session), shift_at(session)
    make_availability(session, shift, employee)

    edit = service.add_assignment(
        session, manager, NEXT_WEEK, shift_id=shift.id, user_id=employee.id
    )

    stored = session.get(Assignment, edit.assignment.id)
    assert (stored.schedule_id, stored.shift_id, stored.user_id) == (
        schedule.id,
        shift.id,
        employee.id,
    )
    assert edit.warnings == []
    assert edit.user.id == employee.id and edit.shift.id == shift.id


def test_add_works_on_a_published_schedule(session: Session, manager: User, employee: User) -> None:
    make_schedule(session, status=ScheduleStatus.published)
    shift = shift_at(session)
    make_availability(session, shift, employee)

    edit = service.add_assignment(
        session, manager, NEXT_WEEK, shift_id=shift.id, user_id=employee.id
    )

    assert edit.assignment.id is not None


# --- add: authorization and lookups ---


def test_add_is_for_managers_only_even_for_a_missing_schedule(
    session: Session, employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.add_assignment(session, employee, NEXT_WEEK, shift_id=1, user_id=1)


def test_add_needs_a_schedule_for_the_week(session: Session, manager: User, employee: User) -> None:
    shift = shift_at(session)

    with pytest.raises(NotFound) as raised:
        service.add_assignment(session, manager, NEXT_WEEK, shift_id=shift.id, user_id=employee.id)

    assert raised.value.code == ErrorCode.schedule_not_found


def test_add_rejects_a_week_start_that_is_not_a_sunday(session: Session, manager: User) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.add_assignment(session, manager, date(2026, 3, 16), shift_id=1, user_id=1)

    assert raised.value.code == ErrorCode.invalid_week_start


def test_add_with_an_unknown_shift_is_not_found(
    session: Session, manager: User, employee: User
) -> None:
    make_schedule(session)

    with pytest.raises(NotFound) as raised:
        service.add_assignment(session, manager, NEXT_WEEK, shift_id=999_999, user_id=employee.id)

    assert raised.value.code == ErrorCode.shift_not_found


def test_add_with_a_shift_of_another_week_is_rejected(
    session: Session, manager: User, employee: User
) -> None:
    make_schedule(session)
    other = shift_at(session, week=THIS_WEEK)

    with pytest.raises(ValidationFailed) as raised:
        service.add_assignment(session, manager, NEXT_WEEK, shift_id=other.id, user_id=employee.id)

    assert raised.value.code == ErrorCode.shift_not_in_week


def test_add_with_an_unknown_user_is_not_found(session: Session, manager: User) -> None:
    make_schedule(session)
    shift = shift_at(session)

    with pytest.raises(NotFound) as raised:
        service.add_assignment(session, manager, NEXT_WEEK, shift_id=shift.id, user_id=999_999)

    assert raised.value.code == ErrorCode.user_not_found


@pytest.mark.parametrize(
    "build",
    [
        lambda session, manager: manager,
        lambda session, manager: make_user(session, role=Role.employee, is_active=False),
    ],
    ids=["a_manager", "a_deactivated_employee"],
)
def test_add_only_places_active_employees(session: Session, manager: User, build) -> None:
    make_schedule(session)
    shift = shift_at(session)
    person = build(session, manager)

    with pytest.raises(ValidationFailed) as raised:
        service.add_assignment(session, manager, NEXT_WEEK, shift_id=shift.id, user_id=person.id)

    assert raised.value.code == ErrorCode.user_not_assignable


# --- add: blocking rules ---


def test_add_twice_is_already_assigned(session: Session, manager: User, employee: User) -> None:
    schedule, shift = make_schedule(session), shift_at(session)
    make_assignment(session, schedule, shift, employee)

    with pytest.raises(Conflict) as raised:
        service.add_assignment(session, manager, NEXT_WEEK, shift_id=shift.id, user_id=employee.id)

    assert raised.value.code == ErrorCode.already_assigned


def test_add_an_overlapping_shift_is_rejected_and_saves_nothing(
    session: Session, manager: User, employee: User
) -> None:
    schedule = make_schedule(session)
    first, second = shift_at(session, start=7), shift_at(session, start=10)
    make_assignment(session, schedule, first, employee)

    with pytest.raises(Conflict) as raised:
        service.add_assignment(session, manager, NEXT_WEEK, shift_id=second.id, user_id=employee.id)

    assert raised.value.code == ErrorCode.shift_overlap
    assert "Monday 07:00" in raised.value.message
    assert count(session) == 1


def test_add_a_shift_inside_the_minimum_rest_is_rejected(
    session: Session, manager: User, employee: User
) -> None:
    schedule = make_schedule(session)
    morning, evening = shift_at(session, start=7), shift_at(session, start=15)  # 0 h gap
    make_assignment(session, schedule, morning, employee)

    with pytest.raises(Conflict) as raised:
        service.add_assignment(
            session, manager, NEXT_WEEK, shift_id=evening.id, user_id=employee.id
        )

    assert raised.value.code == ErrorCode.min_rest_violation
    assert count(session) == 1


def test_add_a_shift_exactly_the_minimum_rest_after_is_allowed(
    session: Session, manager: User, employee: User
) -> None:
    schedule = make_schedule(session)
    morning, night = shift_at(session, start=7), shift_at(session, start=23)  # 8 h gap
    make_assignment(session, schedule, morning, employee)

    service.add_assignment(session, manager, NEXT_WEEK, shift_id=night.id, user_id=employee.id)

    assert count(session) == 2


def test_overlap_wins_over_rest_when_both_apply(
    session: Session, manager: User, employee: User
) -> None:
    schedule = make_schedule(session)
    overlapping, adjacent = shift_at(session, start=10), shift_at(session, start=15)
    target = shift_at(session, start=7)
    make_assignment(session, schedule, adjacent, employee)
    make_assignment(session, schedule, overlapping, employee)

    with pytest.raises(Conflict) as raised:
        service.add_assignment(session, manager, NEXT_WEEK, shift_id=target.id, user_id=employee.id)

    assert raised.value.code == ErrorCode.shift_overlap


# --- add: warnings ---


@pytest.mark.parametrize("status", [None, UNAVAILABLE], ids=["no_answer", "unavailable"])
def test_add_warns_when_the_employee_did_not_say_they_could_work(
    session: Session, manager: User, employee: User, status
) -> None:
    make_schedule(session)
    shift = shift_at(session)
    if status is not None:
        make_availability(session, shift, employee, status)

    edit = service.add_assignment(
        session, manager, NEXT_WEEK, shift_id=shift.id, user_id=employee.id
    )

    assert codes(edit) == ["availability_ignored"]
    assert count(session) == 1


@pytest.mark.parametrize("status", [AVAILABLE, PREFERRED])
def test_add_does_not_warn_when_the_employee_said_they_could_work(
    session: Session, manager: User, employee: User, status
) -> None:
    make_schedule(session)
    shift = shift_at(session)
    make_availability(session, shift, employee, status)

    edit = service.add_assignment(
        session, manager, NEXT_WEEK, shift_id=shift.id, user_id=employee.id
    )

    assert edit.warnings == []


def test_add_warns_beyond_the_max_shifts_per_week_but_saves(
    session: Session, manager: User, employee: User
) -> None:
    schedule = make_schedule(session)
    for weekday in range(5):
        make_assignment(session, schedule, shift_at(session, weekday=weekday), employee)
    sixth = shift_at(session, weekday=5)
    make_availability(session, sixth, employee)

    edit = service.add_assignment(
        session, manager, NEXT_WEEK, shift_id=sixth.id, user_id=employee.id
    )

    assert codes(edit) == ["max_shifts_exceeded"]
    assert count(session) == 6


def test_add_warns_when_the_shift_is_already_fully_staffed(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    schedule = make_schedule(session)
    shift = shift_at(session, staff=1)
    make_assignment(session, schedule, shift, other_employee)
    make_availability(session, shift, employee)

    edit = service.add_assignment(
        session, manager, NEXT_WEEK, shift_id=shift.id, user_id=employee.id
    )

    assert codes(edit) == ["shift_overstaffed"]


def test_add_can_report_several_warnings_at_once(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    schedule = make_schedule(session)
    shift = shift_at(session, staff=1)
    make_assignment(session, schedule, shift, other_employee)

    edit = service.add_assignment(
        session, manager, NEXT_WEEK, shift_id=shift.id, user_id=employee.id
    )

    assert codes(edit) == ["availability_ignored", "shift_overstaffed"]


# --- replace ---


def test_replace_swaps_the_employee_and_keeps_the_assignment(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    schedule, shift = make_schedule(session), shift_at(session)
    assignment = make_assignment(session, schedule, shift, employee)
    make_availability(session, shift, other_employee)

    edit = service.replace_assignment(
        session, manager, NEXT_WEEK, assignment.id, user_id=other_employee.id
    )

    assert edit.assignment.id == assignment.id
    assert session.get(Assignment, assignment.id).user_id == other_employee.id
    assert edit.warnings == []


def test_replace_applies_the_blocking_rules_to_the_new_employee(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    schedule = make_schedule(session)
    mine, theirs = shift_at(session, start=7), shift_at(session, start=10)
    assignment = make_assignment(session, schedule, mine, employee)
    make_assignment(session, schedule, theirs, other_employee)

    with pytest.raises(Conflict) as raised:
        service.replace_assignment(
            session, manager, NEXT_WEEK, assignment.id, user_id=other_employee.id
        )

    assert raised.value.code == ErrorCode.shift_overlap
    assert session.get(Assignment, assignment.id).user_id == employee.id


def test_replace_warns_about_availability(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    schedule, shift = make_schedule(session), shift_at(session)
    assignment = make_assignment(session, schedule, shift, employee)

    edit = service.replace_assignment(
        session, manager, NEXT_WEEK, assignment.id, user_id=other_employee.id
    )

    assert codes(edit) == ["availability_ignored"]


def test_replace_with_the_same_employee_is_already_assigned(
    session: Session, manager: User, employee: User
) -> None:
    schedule, shift = make_schedule(session), shift_at(session)
    assignment = make_assignment(session, schedule, shift, employee)

    with pytest.raises(Conflict) as raised:
        service.replace_assignment(session, manager, NEXT_WEEK, assignment.id, user_id=employee.id)

    assert raised.value.code == ErrorCode.already_assigned


def test_replace_with_an_employee_already_on_that_shift_is_already_assigned(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    schedule, shift = make_schedule(session), shift_at(session)
    assignment = make_assignment(session, schedule, shift, employee)
    make_assignment(session, schedule, shift, other_employee)

    with pytest.raises(Conflict) as raised:
        service.replace_assignment(
            session, manager, NEXT_WEEK, assignment.id, user_id=other_employee.id
        )

    assert raised.value.code == ErrorCode.already_assigned


def test_replace_of_an_unknown_assignment_is_not_found(
    session: Session, manager: User, employee: User
) -> None:
    make_schedule(session)

    with pytest.raises(NotFound) as raised:
        service.replace_assignment(session, manager, NEXT_WEEK, 999_999, user_id=employee.id)

    assert raised.value.code == ErrorCode.assignment_not_found


def test_replace_of_an_assignment_from_another_week_is_not_found(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    make_schedule(session)
    other_schedule = make_schedule(session, week_start=THIS_WEEK)
    other = make_assignment(session, other_schedule, shift_at(session, week=THIS_WEEK), employee)

    with pytest.raises(NotFound) as raised:
        service.replace_assignment(session, manager, NEXT_WEEK, other.id, user_id=other_employee.id)

    assert raised.value.code == ErrorCode.assignment_not_found


def test_replace_is_for_managers_only(
    session: Session, employee: User, other_employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.replace_assignment(session, employee, NEXT_WEEK, 1, user_id=other_employee.id)


# --- remove ---


def test_remove_deletes_only_that_assignment(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    schedule, shift = make_schedule(session), shift_at(session)
    gone = make_assignment(session, schedule, shift, employee)
    kept = make_assignment(session, schedule, shift, other_employee)

    service.remove_assignment(session, manager, NEXT_WEEK, gone.id)

    assert [row.id for row in session.query(Assignment)] == [kept.id]


def test_remove_of_an_unknown_assignment_is_not_found(session: Session, manager: User) -> None:
    make_schedule(session)

    with pytest.raises(NotFound) as raised:
        service.remove_assignment(session, manager, NEXT_WEEK, 999_999)

    assert raised.value.code == ErrorCode.assignment_not_found


def test_remove_of_an_assignment_from_another_week_is_not_found(
    session: Session, manager: User, employee: User
) -> None:
    make_schedule(session)
    other_schedule = make_schedule(session, week_start=THIS_WEEK)
    other = make_assignment(session, other_schedule, shift_at(session, week=THIS_WEEK), employee)

    with pytest.raises(NotFound):
        service.remove_assignment(session, manager, NEXT_WEEK, other.id)

    assert session.get(Assignment, other.id) is not None


def test_remove_is_for_managers_only_and_keeps_the_assignment(
    session: Session, employee: User
) -> None:
    schedule, shift = make_schedule(session), shift_at(session)
    assignment = make_assignment(session, schedule, shift, employee)

    with pytest.raises(Forbidden):
        service.remove_assignment(session, employee, NEXT_WEEK, assignment.id)

    assert count(session) == 1
    assert session.query(Schedule).count() == 1
