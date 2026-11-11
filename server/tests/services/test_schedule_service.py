"""Generating a draft schedule with the solver, proposing without saving, and reading a schedule
(product-definition §5.2, architecture §6.2)."""

from datetime import date, time, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.enums import AvailabilityStatus, Role, ScheduleStatus
from app.core.errors import Conflict, ErrorCode, Forbidden, NotFound, ValidationFailed
from app.models import Assignment, Schedule, User
from app.scheduler import Constraint, SchedulingRules, TraceKind
from app.services import schedule_service as service
from app.services.schedule_service import DayOff
from tests.factories import (
    NEXT_WEEK,
    NOW,
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


def assigned(session: Session, shift_id: int) -> set[int]:
    rows = session.query(Assignment).filter(Assignment.shift_id == shift_id)
    return {row.user_id for row in rows}


def monday_shift(session: Session, *, staff: int = 1, week: date = NEXT_WEEK, hour: int = 7):
    template = make_shift_template(
        session,
        weekday=1,
        start_time=time(hour, 0),
        end_time=time(hour + 8, 0),
        required_staff=staff,
    )
    return make_shift(session, template, week_start=week)


# --- generate: what ends up in the draft ---


def test_generate_stores_a_draft_with_the_solvers_assignments(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    shift = monday_shift(session, staff=2)
    make_availability(session, shift, employee)
    make_availability(session, shift, other_employee, PREFERRED)

    outcome = service.generate_schedule(session, manager, NEXT_WEEK)

    schedule = outcome.view.schedule
    assert (schedule.week_start, schedule.status, schedule.published_at) == (
        NEXT_WEEK,
        ScheduleStatus.draft,
        None,
    )
    assert assigned(session, shift.id) == {employee.id, other_employee.id}
    assert outcome.proposal.result.unfilled == ()
    assert outcome.proposal.sentences == []


def test_generate_never_assigns_unavailable_or_unanswered_employees(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    shift = monday_shift(session, staff=2)
    make_availability(session, shift, employee, UNAVAILABLE)
    third = make_user(session, role=Role.employee)  # never answered
    make_availability(session, shift, other_employee)

    outcome = service.generate_schedule(session, manager, NEXT_WEEK)

    assert assigned(session, shift.id) == {other_employee.id}
    assert third.id not in assigned(session, shift.id)
    assert outcome.proposal.sentences == ["Monday 07:00 needs 2, only 1 available"]


def test_generate_ignores_answers_of_deactivated_users_and_managers(
    session: Session, manager: User, employee: User
) -> None:
    shift = monday_shift(session, staff=3)
    gone = make_user(session, role=Role.employee, is_active=False)
    make_availability(session, shift, gone)
    make_availability(session, shift, manager)
    make_availability(session, shift, employee)

    service.generate_schedule(session, manager, NEXT_WEEK)

    assert assigned(session, shift.id) == {employee.id}


def test_generate_applies_the_minimum_rest(session: Session, manager: User, employee: User) -> None:
    morning = monday_shift(session, hour=7)
    evening = monday_shift(session, hour=15)
    make_availability(session, morning, employee)
    make_availability(session, evening, employee)

    outcome = service.generate_schedule(session, manager, NEXT_WEEK)

    assert assigned(session, morning.id) == {employee.id}
    assert assigned(session, evening.id) == set()
    assert outcome.proposal.sentences == [
        "Monday 15:00 needs 1, only 0 available; Eli Employee excluded by minimum rest"
    ]


def test_generate_replaces_the_current_draft(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    shift = monday_shift(session)
    first_answer = make_availability(session, shift, employee)
    first = service.generate_schedule(session, manager, NEXT_WEEK)
    first_answer.status = UNAVAILABLE
    make_availability(session, shift, other_employee)

    second = service.generate_schedule(session, manager, NEXT_WEEK)

    assert second.view.schedule.id == first.view.schedule.id
    assert assigned(session, shift.id) == {other_employee.id}
    assert session.query(Assignment).count() == 1
    assert session.query(Schedule).count() == 1


def test_generate_leaves_other_weeks_alone(session: Session, manager: User, employee: User) -> None:
    other_week = make_schedule(session, week_start=THIS_WEEK)
    other_shift = monday_shift(session, week=THIS_WEEK)
    make_assignment(session, other_week, other_shift, employee)
    shift = monday_shift(session)
    make_availability(session, shift, employee)

    service.generate_schedule(session, manager, NEXT_WEEK)

    assert assigned(session, other_shift.id) == {employee.id}


# --- generate: refusals ---


def test_generate_never_replaces_a_published_schedule(
    session: Session, manager: User, employee: User
) -> None:
    shift = monday_shift(session)
    make_availability(session, shift, employee)
    published = make_schedule(session, status=ScheduleStatus.published)
    make_assignment(session, published, shift, employee)

    with pytest.raises(Conflict) as raised:
        service.generate_schedule(session, manager, NEXT_WEEK)

    assert raised.value.code == ErrorCode.schedule_published
    assert assigned(session, shift.id) == {employee.id}


def test_generate_needs_shifts_for_the_week(session: Session, manager: User) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.generate_schedule(session, manager, NEXT_WEEK)

    assert raised.value.code == ErrorCode.no_shifts_for_week
    assert session.query(Schedule).count() == 0


def test_generate_rejects_a_week_start_that_is_not_a_sunday(
    session: Session, manager: User
) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.generate_schedule(session, manager, date(2026, 3, 16))

    assert raised.value.code == ErrorCode.invalid_week_start


def test_generate_is_for_managers_only_and_writes_nothing(session: Session, employee: User) -> None:
    make_availability(session, monday_shift(session), employee)

    with pytest.raises(Forbidden):
        service.generate_schedule(session, employee, NEXT_WEEK)

    assert session.query(Schedule).count() == 0


# --- propose (dry run) ---


def test_propose_returns_the_result_without_saving_anything(
    session: Session, manager: User, employee: User
) -> None:
    shift = monday_shift(session)
    make_availability(session, shift, employee)

    proposal = service.propose_schedule(session, manager, NEXT_WEEK)

    assert [(a.shift_id, a.employee_id) for a in proposal.result.assignments] == [
        (shift.id, employee.id)
    ]
    assert session.query(Schedule).count() == 0
    assert session.query(Assignment).count() == 0


def test_propose_works_on_a_published_week(session: Session, manager: User, employee: User) -> None:
    shift = monday_shift(session)
    make_availability(session, shift, employee)
    make_schedule(session, status=ScheduleStatus.published)

    proposal = service.propose_schedule(session, manager, NEXT_WEEK)

    assert len(proposal.result.assignments) == 1


def test_propose_can_try_other_rules_and_record_a_trace(
    session: Session, manager: User, employee: User
) -> None:
    morning, evening = monday_shift(session, hour=7), monday_shift(session, hour=15)
    make_availability(session, morning, employee)
    make_availability(session, evening, employee)

    relaxed = service.propose_schedule(
        session, manager, NEXT_WEEK, rules=SchedulingRules(min_rest_hours=0), trace=True
    )

    assert relaxed.result.unfilled == ()
    assert any(event.kind is TraceKind.assign for event in relaxed.result.trace)


def test_propose_is_for_managers_only(session: Session, employee: User) -> None:
    monday_shift(session)

    with pytest.raises(Forbidden):
        service.propose_schedule(session, employee, NEXT_WEEK)


def test_a_proposal_reports_why_a_slot_is_unfilled(
    session: Session, manager: User, employee: User
) -> None:
    shift = monday_shift(session)
    make_availability(session, shift, employee, UNAVAILABLE)

    proposal = service.propose_schedule(session, manager, NEXT_WEEK)

    slot = proposal.result.unfilled[0]
    assert (slot.shift_id, slot.missing) == (shift.id, 1)
    assert slot.reasons[0].constraint is Constraint.availability


# --- get ---


def test_a_manager_reads_a_draft_with_its_assignments_and_shifts(
    session: Session, manager: User, employee: User
) -> None:
    shift = monday_shift(session)
    schedule = make_schedule(session)
    assignment = make_assignment(session, schedule, shift, employee)

    view = service.get_schedule(session, manager, NEXT_WEEK)

    assert view.schedule.id == schedule.id
    assert [a.id for a in view.assignments] == [assignment.id]
    assert [s.id for s in view.shifts] == [shift.id]
    assert view.users[employee.id].name == "Eli Employee"


def test_an_employee_reads_a_published_schedule(session: Session, employee: User) -> None:
    schedule = make_schedule(session, status=ScheduleStatus.published)

    assert service.get_schedule(session, employee, NEXT_WEEK).schedule.id == schedule.id


def test_an_employee_cannot_see_that_a_draft_exists(session: Session, employee: User) -> None:
    make_schedule(session)

    with pytest.raises(NotFound) as raised:
        service.get_schedule(session, employee, NEXT_WEEK)

    assert raised.value.code == ErrorCode.schedule_not_found


@pytest.mark.parametrize("role", [Role.manager, Role.employee])
def test_a_week_without_a_schedule_is_not_found(session: Session, role: Role) -> None:
    reader = make_user(session, role=role)

    with pytest.raises(NotFound) as raised:
        service.get_schedule(session, reader, NEXT_WEEK)

    assert raised.value.code == ErrorCode.schedule_not_found


def test_get_orders_assignments_by_shift_time_then_name(session: Session, manager: User) -> None:
    schedule = make_schedule(session)
    early = monday_shift(session, hour=7)
    late = monday_shift(session, hour=15)
    zed = make_user(session, role=Role.employee, name="Zed")
    amy = make_user(session, role=Role.employee, name="Amy")
    first = make_assignment(session, schedule, late, amy)
    second = make_assignment(session, schedule, early, zed)
    third = make_assignment(session, schedule, early, amy)

    view = service.get_schedule(session, manager, NEXT_WEEK)

    assert [a.id for a in view.assignments] == [third.id, second.id, first.id]


def test_get_rejects_a_week_start_that_is_not_a_sunday(session: Session, manager: User) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.get_schedule(session, manager, date(2026, 3, 16))

    assert raised.value.code == ErrorCode.invalid_week_start


# --- publish ---


def test_publish_marks_the_draft_published_at_the_given_time(
    session: Session, manager: User
) -> None:
    make_schedule(session)

    view = service.publish_schedule(session, manager, NEXT_WEEK, now=NOW)

    assert view.schedule.status is ScheduleStatus.published
    assert view.schedule.published_at == NOW


def test_publish_makes_the_schedule_visible_to_employees(
    session: Session, manager: User, employee: User
) -> None:
    make_schedule(session)
    service.publish_schedule(session, manager, NEXT_WEEK, now=NOW)

    assert service.get_schedule(session, employee, NEXT_WEEK).schedule.week_start == NEXT_WEEK


def test_publish_of_an_empty_draft_is_allowed(session: Session, manager: User) -> None:
    make_schedule(session)

    assert service.publish_schedule(session, manager, NEXT_WEEK, now=NOW).assignments == []


def test_publish_twice_is_schedule_published_and_keeps_the_first_time(
    session: Session, manager: User
) -> None:
    make_schedule(session, status=ScheduleStatus.published, published_at=NOW)

    with pytest.raises(Conflict) as raised:
        service.publish_schedule(session, manager, NEXT_WEEK, now=NOW + timedelta(hours=1))

    assert raised.value.code == ErrorCode.schedule_published
    assert session.query(Schedule).one().published_at == NOW


def test_publish_without_a_schedule_is_not_found(session: Session, manager: User) -> None:
    with pytest.raises(NotFound) as raised:
        service.publish_schedule(session, manager, NEXT_WEEK, now=NOW)

    assert raised.value.code == ErrorCode.schedule_not_found


def test_publish_is_for_managers_only_and_changes_nothing(session: Session, employee: User) -> None:
    make_schedule(session)

    with pytest.raises(Forbidden):
        service.publish_schedule(session, employee, NEXT_WEEK, now=NOW)

    assert session.query(Schedule).one().status is ScheduleStatus.draft


def test_publish_rejects_a_week_start_that_is_not_a_sunday(session: Session, manager: User) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.publish_schedule(session, manager, date(2026, 3, 16), now=NOW)

    assert raised.value.code == ErrorCode.invalid_week_start


# --- days off: "Dana can't work Tuesday" (plan 004) ---

MONDAY = NEXT_WEEK + timedelta(days=1)
TUESDAY = NEXT_WEEK + timedelta(days=2)


def shift_on(session: Session, weekday: int, start: time, end: time, *, staff: int = 1):
    template = make_shift_template(
        session, weekday=weekday, start_time=start, end_time=end, required_staff=staff
    )
    return make_shift(session, template)


def test_generate_with_a_day_off_does_not_assign_that_person_on_that_day(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    shift = monday_shift(session)
    make_availability(session, shift, employee, PREFERRED)
    make_availability(session, shift, other_employee)

    service.generate_schedule(
        session, manager, NEXT_WEEK, unavailable=[DayOff(employee.id, MONDAY)]
    )

    assert assigned(session, shift.id) == {other_employee.id}


def test_a_day_off_leaves_the_persons_other_days_alone(
    session: Session, manager: User, employee: User
) -> None:
    monday = shift_on(session, 1, time(7), time(15))
    tuesday = shift_on(session, 2, time(7), time(15))
    make_availability(session, monday, employee)
    make_availability(session, tuesday, employee)

    service.generate_schedule(
        session, manager, NEXT_WEEK, unavailable=[DayOff(employee.id, MONDAY)]
    )

    assert assigned(session, monday.id) == set()
    assert assigned(session, tuesday.id) == {employee.id}


def test_a_shift_belongs_to_the_local_day_it_starts_on(
    session: Session, manager: User, employee: User
) -> None:
    night = shift_on(session, 1, time(23), time(7))  # Monday 23:00, ends Tuesday morning
    early = shift_on(session, 1, time(0, 30), time(6))  # 22:30 UTC on Sunday, Monday locally
    make_availability(session, night, employee)
    make_availability(session, early, employee)

    service.generate_schedule(
        session, manager, NEXT_WEEK, unavailable=[DayOff(employee.id, MONDAY)]
    )

    assert assigned(session, night.id) == set()
    assert assigned(session, early.id) == set()


def test_a_day_off_on_the_day_a_night_shift_ends_does_not_block_it(
    session: Session, manager: User, employee: User
) -> None:
    night = shift_on(session, 1, time(23), time(7))
    make_availability(session, night, employee)

    service.generate_schedule(
        session, manager, NEXT_WEEK, unavailable=[DayOff(employee.id, TUESDAY)]
    )

    assert assigned(session, night.id) == {employee.id}


def test_the_same_day_off_twice_is_the_same_as_once(
    session: Session, manager: User, employee: User
) -> None:
    shift = monday_shift(session)
    make_availability(session, shift, employee)

    proposal = service.propose_schedule(
        session,
        manager,
        NEXT_WEEK,
        unavailable=[DayOff(employee.id, MONDAY), DayOff(employee.id, MONDAY)],
    )

    assert proposal.result.assignments == ()


def test_propose_explains_a_slot_left_empty_by_a_day_off_and_saves_nothing(
    session: Session, manager: User, employee: User
) -> None:
    shift = monday_shift(session)
    make_availability(session, shift, employee)

    proposal = service.propose_schedule(
        session, manager, NEXT_WEEK, unavailable=[DayOff(employee.id, MONDAY)]
    )

    assert proposal.sentences == [
        "Monday 07:00 needs 1, only 0 available; Eli Employee excluded by a requested day off"
    ]
    assert session.query(Schedule).count() == 0
    assert session.query(Assignment).count() == 0


def test_a_day_off_outside_the_week_is_rejected_and_nothing_is_saved(
    session: Session, manager: User, employee: User
) -> None:
    monday_shift(session)

    with pytest.raises(ValidationFailed) as raised:
        service.generate_schedule(
            session,
            manager,
            NEXT_WEEK,
            unavailable=[DayOff(employee.id, NEXT_WEEK + timedelta(days=7))],
        )

    assert raised.value.code == ErrorCode.validation_error
    assert session.query(Schedule).count() == 0


@pytest.mark.parametrize("who", ["unknown", "manager", "deactivated"])
def test_a_day_off_for_someone_who_cannot_be_scheduled_is_rejected(
    session: Session, manager: User, who: str
) -> None:
    monday_shift(session)
    user_id = {
        "unknown": 987654,
        "manager": manager.id,
        "deactivated": make_user(session, role=Role.employee, is_active=False).id,
    }[who]

    with pytest.raises(ValidationFailed) as raised:
        service.propose_schedule(session, manager, NEXT_WEEK, unavailable=[DayOff(user_id, MONDAY)])

    assert raised.value.code == ErrorCode.user_not_assignable


def test_days_off_are_for_managers_only(session: Session, employee: User) -> None:
    monday_shift(session)

    with pytest.raises(Forbidden):
        service.generate_schedule(
            session, employee, NEXT_WEEK, unavailable=[DayOff(employee.id, MONDAY)]
        )
