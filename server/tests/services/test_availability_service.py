"""Availability: who may read and answer, the lock, and the validation of answers
(product-definition §5.1)."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.enums import AvailabilityStatus, Role, ScheduleStatus
from app.core.errors import Conflict, ErrorCode, Forbidden, NotFound, ValidationFailed
from app.models import Availability, User
from app.services import availability_service as service
from tests.factories import (
    NEXT_WEEK,
    NOW,
    THIS_WEEK,
    make_availability,
    make_schedule,
    make_shift,
    make_shift_template,
    make_user,
)

AVAILABLE = AvailabilityStatus.available
PREFERRED = AvailabilityStatus.preferred
UNAVAILABLE = AvailabilityStatus.unavailable


def statuses(rows: list[Availability]) -> dict[tuple[int, int], AvailabilityStatus]:
    return {(row.shift_id, row.user_id): row.status for row in rows}


# --- reading ---


def test_an_employee_reads_only_their_own_answers(
    session: Session, employee: User, other_employee: User
) -> None:
    shift = make_shift(session)
    mine = make_availability(session, shift, employee, PREFERRED)
    make_availability(session, shift, other_employee)

    found = service.list_availabilities(session, employee, NEXT_WEEK)

    assert [row.id for row in found] == [mine.id]


def test_an_employee_may_not_read_another_employees_answers(
    session: Session, employee: User, other_employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.list_availabilities(session, employee, NEXT_WEEK, user_id=other_employee.id)


def test_an_employee_asking_for_an_unknown_user_is_forbidden_not_not_found(
    session: Session, employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.list_availabilities(session, employee, NEXT_WEEK, user_id=999_999)


def test_an_employee_may_name_themselves_explicitly(session: Session, employee: User) -> None:
    make_availability(session, make_shift(session), employee)

    assert len(service.list_availabilities(session, employee, NEXT_WEEK, user_id=employee.id)) == 1


def test_a_manager_reads_one_employees_answers(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    shift = make_shift(session)
    make_availability(session, shift, employee)
    make_availability(session, shift, other_employee)

    found = service.list_availabilities(session, manager, NEXT_WEEK, user_id=employee.id)

    assert [row.user_id for row in found] == [employee.id]


def test_a_manager_without_a_user_reads_the_whole_teams_answers(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    shift = make_shift(session)
    make_availability(session, shift, employee)
    make_availability(session, shift, other_employee)

    found = service.list_availabilities(session, manager, NEXT_WEEK)

    assert {row.user_id for row in found} == {employee.id, other_employee.id}


def test_reading_returns_only_the_requested_week(session: Session, employee: User) -> None:
    template = make_shift_template(session)
    make_availability(session, make_shift(session, template, week_start=NEXT_WEEK), employee)
    make_availability(session, make_shift(session, template, week_start=THIS_WEEK), employee)

    found = service.list_availabilities(session, employee, NEXT_WEEK)

    assert len(found) == 1


def test_a_manager_asking_for_an_unknown_user_gets_not_found(
    session: Session, manager: User
) -> None:
    with pytest.raises(NotFound) as raised:
        service.list_availabilities(session, manager, NEXT_WEEK, user_id=999_999)

    assert raised.value.code == ErrorCode.user_not_found


def test_reading_a_past_week_is_allowed(session: Session, employee: User) -> None:
    past = date(2026, 3, 1)

    assert service.list_availabilities(session, employee, past) == []


def test_reading_rejects_a_week_start_that_is_not_a_sunday(
    session: Session, employee: User
) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.list_availabilities(session, employee, date(2026, 3, 16))

    assert raised.value.code == ErrorCode.invalid_week_start


# --- answering ---


def test_an_employee_answers_for_themselves(session: Session, employee: User) -> None:
    first, second = make_shift(session), make_shift(session)

    saved = service.set_availabilities(
        session, employee, NEXT_WEEK, {first.id: AVAILABLE, second.id: PREFERRED}, now=NOW
    )

    assert statuses(saved) == {
        (first.id, employee.id): AVAILABLE,
        (second.id, employee.id): PREFERRED,
    }


def test_answering_again_updates_the_row_and_leaves_other_answers_alone(
    session: Session, employee: User
) -> None:
    first, second = make_shift(session), make_shift(session)
    service.set_availabilities(
        session, employee, NEXT_WEEK, {first.id: AVAILABLE, second.id: AVAILABLE}, now=NOW
    )

    saved = service.set_availabilities(
        session, employee, NEXT_WEEK, {first.id: UNAVAILABLE}, now=NOW
    )

    assert statuses(saved) == {
        (first.id, employee.id): UNAVAILABLE,
        (second.id, employee.id): AVAILABLE,
    }
    assert session.query(Availability).count() == 2


def test_an_explicit_unavailable_answer_is_stored(session: Session, employee: User) -> None:
    shift = make_shift(session)

    service.set_availabilities(session, employee, NEXT_WEEK, {shift.id: UNAVAILABLE}, now=NOW)

    assert session.query(Availability).one().status is UNAVAILABLE


def test_an_employee_may_not_answer_for_someone_else(
    session: Session, employee: User, other_employee: User
) -> None:
    shift = make_shift(session)

    with pytest.raises(Forbidden):
        service.set_availabilities(
            session, employee, NEXT_WEEK, {shift.id: AVAILABLE}, user_id=other_employee.id, now=NOW
        )

    assert session.query(Availability).count() == 0


def test_a_manager_answers_for_an_employee(session: Session, manager: User, employee: User) -> None:
    shift = make_shift(session)

    saved = service.set_availabilities(
        session, manager, NEXT_WEEK, {shift.id: PREFERRED}, user_id=employee.id, now=NOW
    )

    assert statuses(saved) == {(shift.id, employee.id): PREFERRED}


@pytest.mark.parametrize(
    "target",
    [
        lambda session, manager: manager,
        lambda session, manager: make_user(session, role=Role.employee, is_active=False),
    ],
    ids=["a_manager", "a_deactivated_employee"],
)
def test_answers_are_only_kept_for_active_employees(
    session: Session, manager: User, target
) -> None:
    shift = make_shift(session)
    person = target(session, manager)

    with pytest.raises(ValidationFailed) as raised:
        service.set_availabilities(
            session, manager, NEXT_WEEK, {shift.id: AVAILABLE}, user_id=person.id, now=NOW
        )

    assert raised.value.code == ErrorCode.user_not_assignable


def test_answering_for_an_unknown_user_is_not_found(session: Session, manager: User) -> None:
    shift = make_shift(session)

    with pytest.raises(NotFound) as raised:
        service.set_availabilities(
            session, manager, NEXT_WEEK, {shift.id: AVAILABLE}, user_id=999_999, now=NOW
        )

    assert raised.value.code == ErrorCode.user_not_found


# --- the lock ---


@pytest.mark.parametrize("status", list(ScheduleStatus), ids=["draft", "published"])
def test_an_employee_cannot_answer_once_a_schedule_exists(
    session: Session, employee: User, status: ScheduleStatus
) -> None:
    shift = make_shift(session)
    make_schedule(session, status=status)

    with pytest.raises(Conflict) as raised:
        service.set_availabilities(session, employee, NEXT_WEEK, {shift.id: AVAILABLE}, now=NOW)

    assert raised.value.code == ErrorCode.availability_locked


def test_a_manager_can_still_answer_after_the_schedule_exists(
    session: Session, manager: User, employee: User
) -> None:
    shift = make_shift(session)
    make_schedule(session)

    saved = service.set_availabilities(
        session, manager, NEXT_WEEK, {shift.id: AVAILABLE}, user_id=employee.id, now=NOW
    )

    assert len(saved) == 1


def test_an_employee_cannot_answer_for_a_past_week(session: Session, employee: User) -> None:
    past_week = date(2026, 3, 1)
    shift = make_shift(session, week_start=past_week)

    with pytest.raises(Conflict) as raised:
        service.set_availabilities(session, employee, past_week, {shift.id: AVAILABLE}, now=NOW)

    assert raised.value.code == ErrorCode.availability_locked


def test_an_employee_can_answer_for_the_current_week_until_it_is_scheduled(
    session: Session, employee: User
) -> None:
    shift = make_shift(session, week_start=THIS_WEEK)  # NOW is Monday of this week

    saved = service.set_availabilities(session, employee, THIS_WEEK, {shift.id: AVAILABLE}, now=NOW)

    assert len(saved) == 1


def test_a_manager_can_answer_for_a_past_week(
    session: Session, manager: User, employee: User
) -> None:
    past_week = date(2026, 3, 1)
    shift = make_shift(session, week_start=past_week)

    saved = service.set_availabilities(
        session, manager, past_week, {shift.id: AVAILABLE}, user_id=employee.id, now=NOW
    )

    assert len(saved) == 1


# --- validation of the answers ---


def test_an_unknown_shift_is_not_found(session: Session, employee: User) -> None:
    with pytest.raises(NotFound) as raised:
        service.set_availabilities(session, employee, NEXT_WEEK, {999_999: AVAILABLE}, now=NOW)

    assert raised.value.code == ErrorCode.shift_not_found


def test_a_shift_of_another_week_is_rejected(session: Session, employee: User) -> None:
    other_week = make_shift(session, week_start=THIS_WEEK)

    with pytest.raises(ValidationFailed) as raised:
        service.set_availabilities(
            session, employee, NEXT_WEEK, {other_week.id: AVAILABLE}, now=NOW
        )

    assert raised.value.code == ErrorCode.shift_not_in_week


def test_one_bad_shift_means_nothing_is_saved(session: Session, employee: User) -> None:
    good = make_shift(session)

    with pytest.raises(NotFound):
        service.set_availabilities(
            session, employee, NEXT_WEEK, {good.id: AVAILABLE, 999_999: AVAILABLE}, now=NOW
        )

    assert session.query(Availability).count() == 0


def test_answering_rejects_a_week_start_that_is_not_a_sunday(
    session: Session, employee: User
) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.set_availabilities(session, employee, date(2026, 3, 16), {1: AVAILABLE}, now=NOW)

    assert raised.value.code == ErrorCode.invalid_week_start
