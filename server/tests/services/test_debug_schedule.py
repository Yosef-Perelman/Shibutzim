"""The debug-schedule report: why a week could not be filled and what could be relaxed.

It is a read-only developer tool (`scripts/debug_schedule.py`) on top of `propose_schedule`.
"""

from datetime import time

import pytest
from sqlalchemy.orm import Session

from app.core.enums import AvailabilityStatus, Role
from app.core.errors import ErrorCode, ValidationFailed
from app.models import Assignment, Schedule, User
from app.scheduler import SchedulingRules
from scripts import debug_schedule
from tests.factories import (
    NEXT_WEEK,
    make_availability,
    make_shift,
    make_shift_template,
    make_user,
)

AVAILABLE = AvailabilityStatus.available


def person(session: Session, name: str) -> User:
    return make_user(session, role=Role.employee, name=name)


def unfillable_week(session: Session) -> dict[str, User]:
    """Monday night needs Dana alone; Tuesday 07:00 needs 3 but Dana's rest blocks her."""
    night = make_shift(
        session,
        make_shift_template(
            session, weekday=1, start_time=time(23), end_time=time(7), required_staff=1
        ),
    )
    morning = make_shift(
        session,
        make_shift_template(
            session, weekday=2, start_time=time(7), end_time=time(15), required_staff=3
        ),
    )
    people = {name: person(session, name) for name in ("Dana", "Noa", "Omer", "Tamar")}
    make_availability(session, night, people["Dana"])
    for name in ("Dana", "Noa", "Omer"):
        make_availability(session, morning, people[name])
    return people


def report(session: Session, manager: User, rules: SchedulingRules | None = None) -> str:
    return debug_schedule.build_report(
        session, manager, NEXT_WEEK, rules or SchedulingRules.default()
    )


def test_the_report_gives_the_sentence_for_each_unfilled_slot(
    session: Session, manager: User
) -> None:
    unfillable_week(session)

    text = report(session, manager)

    assert "Positions filled: 3 of 4" in text
    assert "Tuesday 07:00 needs 3, only 2 available; Dana excluded by minimum rest" in text


def test_the_report_names_the_conflicting_shift_behind_each_exclusion(
    session: Session, manager: User
) -> None:
    unfillable_week(session)

    text = report(session, manager)

    assert "Dana: minimum rest with Monday 23:00" in text


def test_the_report_lists_who_did_not_answer_available(session: Session, manager: User) -> None:
    unfillable_week(session)

    assert "Did not answer available: Tamar" in report(session, manager)


def test_the_report_says_what_relaxing_each_rule_would_change(
    session: Session, manager: User
) -> None:
    unfillable_week(session)

    text = report(session, manager)

    assert "if there were no minimum rest: fills 4 of 4 (+1)" in text
    assert "if employees could work 6 shifts a week: no change" in text


def test_the_report_shows_the_rules_it_used(session: Session, manager: User) -> None:
    unfillable_week(session)

    text = report(session, manager, SchedulingRules(min_rest_hours=6, max_shifts_per_week=4))

    assert "minimum rest 6 h, max 4 shifts per week" in text


def test_the_report_summarizes_the_trace(session: Session, manager: User) -> None:
    unfillable_week(session)

    text = report(session, manager)

    assert "Trace:" in text and "placements" in text and "eliminated" in text


def test_the_report_of_a_fully_staffed_week_says_so(
    session: Session, manager: User, employee: User
) -> None:
    shift = make_shift(session, make_shift_template(session, required_staff=1))
    make_availability(session, shift, employee)

    text = report(session, manager)

    assert "Every position is filled." in text
    assert "What if" not in text


def test_the_report_writes_nothing(session: Session, manager: User) -> None:
    unfillable_week(session)

    report(session, manager)

    assert session.query(Schedule).count() == 0
    assert session.query(Assignment).count() == 0


def test_a_week_without_shifts_is_reported_as_an_error(session: Session, manager: User) -> None:
    with pytest.raises(ValidationFailed) as raised:
        report(session, manager)

    assert raised.value.code == ErrorCode.no_shifts_for_week


def test_the_report_lists_an_unanswered_employee_only_as_unanswered(
    session: Session, manager: User
) -> None:
    """Tamar works Monday night and never answered for Tuesday: her rest is not the cause."""
    night = make_shift(
        session,
        make_shift_template(
            session, weekday=1, start_time=time(23), end_time=time(7), required_staff=1
        ),
    )
    morning = make_shift(
        session,
        make_shift_template(
            session, weekday=2, start_time=time(7), end_time=time(15), required_staff=3
        ),
    )
    tamar, dana, noa = person(session, "Tamar"), person(session, "Dana"), person(session, "Noa")
    make_availability(session, night, tamar)
    make_availability(session, morning, dana)
    make_availability(session, morning, noa)

    text = report(session, manager)

    assert "Tuesday 07:00 needs 3, only 2 available" in text
    assert "excluded by" not in text
    assert "Tamar: minimum rest" not in text
    assert "Did not answer available: Tamar" in text
