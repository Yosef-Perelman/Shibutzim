"""The manager tools and the schedule proposal (plan 004). Write tools never write."""

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.assistant.context import ToolContext
from app.assistant.dispatch import call_tool
from app.assistant.llm import FakeLLM
from app.core.enums import AvailabilityStatus, Role, ScheduleStatus
from app.models import Assignment, Schedule, User
from tests.factories import (
    NEXT_WEEK,
    THIS_WEEK,
    make_availability,
    make_schedule,
    make_shift,
    make_shift_template,
    make_time_entry,
    make_user,
)

MONDAY = date(2026, 3, 9)
NEXT_MONDAY = NEXT_WEEK + timedelta(days=1)
WEEK = NEXT_WEEK.isoformat()


def run(session: Session, user: User, tool: str, **args):
    return call_tool(ToolContext(session=session, user=user, llm=FakeLLM([])), tool, args)


def local(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=UTC) - timedelta(hours=2)


def monday_shift(session: Session, *, staff: int = 2, name: str = "Morning"):
    template = make_shift_template(
        session, name=name, weekday=1, start_time=time(7), end_time=time(15), required_staff=staff
    )
    return make_shift(session, template, week_start=NEXT_WEEK)


# --- who_is_available ---


def test_who_is_available_groups_the_names_by_answer(
    session: Session, manager: User, employee: User, other_employee: User
):
    shift = monday_shift(session)
    third = make_user(session, name="Zoe Zed")
    make_availability(session, shift, employee, AvailabilityStatus.preferred)
    make_availability(session, shift, other_employee, AvailabilityStatus.available)
    make_availability(session, shift, third, AvailabilityStatus.unavailable)

    outcome = run(session, manager, "who_is_available", shift_id=shift.id)

    assert outcome.status == "ok"
    assert outcome.content == {
        "shift": {
            "id": shift.id,
            "date": "2026-03-16",
            "weekday": "Monday",
            "name": "Morning",
            "start": "07:00",
            "end": "15:00",
            "required_staff": 2,
        },
        "preferred": ["Eli Employee"],
        "available": ["Dana Other"],
        "unavailable": ["Zoe Zed"],
    }


def test_who_is_available_for_a_missing_shift_is_a_tool_error(session: Session, manager: User):
    outcome = run(session, manager, "who_is_available", shift_id=987654)

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "shift_not_found"


def test_who_is_available_is_refused_for_an_employee(session: Session, employee: User):
    shift = monday_shift(session)

    outcome = run(session, employee, "who_is_available", shift_id=shift.id)

    assert outcome.status == "refused"
    assert outcome.content["error"]["code"] == "forbidden"


# --- get_team_hours ---


def test_get_team_hours_lists_who_worked_with_hours_and_overtime(
    session: Session, manager: User, employee: User, other_employee: User
):
    make_time_entry(session, employee, clock_in=local(MONDAY, 7), duration=timedelta(hours=9))
    make_time_entry(session, other_employee, clock_in=local(MONDAY, 7), duration=timedelta(hours=5))

    outcome = run(session, manager, "get_team_hours", **{"from": "2026-03-09", "to": "2026-03-15"})

    assert outcome.content == {
        "from": "2026-03-09",
        "to": "2026-03-15",
        "total_hours": "14.00",
        "people": [
            {
                "user_id": other_employee.id,
                "name": "Dana Other",
                "hours": "5.00",
                "overtime_hours": "0.00",
                "open_entries": 0,
            },
            {
                "user_id": employee.id,
                "name": "Eli Employee",
                "hours": "9.00",
                "overtime_hours": "1.00",
                "open_entries": 0,
            },
        ],
    }


def test_get_team_hours_leaves_out_people_with_no_hours(session: Session, manager: User):
    outcome = run(session, manager, "get_team_hours", **{"from": "2026-03-09", "to": "2026-03-15"})

    assert outcome.content["people"] == []
    assert outcome.content["total_hours"] == "0.00"


def test_get_team_hours_is_refused_for_an_employee(session: Session, employee: User):
    outcome = run(session, employee, "get_team_hours", **{"from": "2026-03-09", "to": "2026-03-15"})

    assert outcome.status == "refused"


# --- generate_schedule_draft ---


def propose(session: Session, manager: User, **args):
    return run(session, manager, "generate_schedule_draft", week_start=WEEK, **args)


def saved_rows(session: Session) -> tuple[int, int]:
    return session.query(Schedule).count(), session.query(Assignment).count()


def test_a_proposal_names_who_is_off_and_who_covers_the_shift_and_saves_nothing(
    session: Session, manager: User, employee: User, other_employee: User
):
    shift = monday_shift(session, staff=1)
    make_availability(session, shift, employee, AvailabilityStatus.preferred)
    make_availability(session, shift, other_employee)

    outcome = propose(
        session, manager, unavailable=[{"name": "Eli", "day": NEXT_MONDAY.isoformat()}]
    )

    assert outcome.status == "ok"
    assert outcome.proposal == {
        "type": "schedule_draft",
        "week_start": WEEK,
        "unavailable": [
            {"user_id": employee.id, "name": "Eli Employee", "day": NEXT_MONDAY.isoformat()}
        ],
        "summary": "1 of 1 positions filled. Every shift is fully staffed.",
        "filled": 1,
        "required": 1,
        "replaces_draft": False,
        "assignments": [
            {
                "shift_id": shift.id,
                "date": "2026-03-16",
                "weekday": "Monday",
                "name": "Morning",
                "start": "07:00",
                "end": "15:00",
                "people": ["Dana Other"],
            }
        ],
        "unfilled": [],
    }
    assert saved_rows(session) == (0, 0)


def test_the_model_gets_a_compact_result_without_the_full_proposal(
    session: Session, manager: User, employee: User
):
    shift = monday_shift(session)
    make_availability(session, shift, employee)

    outcome = propose(session, manager)

    assert "proposal" not in outcome.content
    assert outcome.content == {
        "summary": "1 of 2 positions filled. 1 shift is short of staff.",
        "filled": 1,
        "required": 2,
        "unfilled": ["Monday 07:00 needs 2, only 1 available"],
        "days_off_applied": [],
        "replaces_draft": False,
        "note": (
            "This is only a proposal. Nothing is saved until the manager confirms it in the app."
        ),
    }


def test_a_day_off_that_leaves_a_slot_empty_is_explained(
    session: Session, manager: User, employee: User
):
    shift = monday_shift(session, staff=1)
    make_availability(session, shift, employee)

    outcome = propose(
        session, manager, unavailable=[{"name": "Eli Employee", "day": NEXT_MONDAY.isoformat()}]
    )

    assert outcome.content["unfilled"] == [
        "Monday 07:00 needs 1, only 0 available; Eli Employee excluded by a requested day off"
    ]
    assert outcome.content["days_off_applied"] == [
        {"name": "Eli Employee", "day": NEXT_MONDAY.isoformat()}
    ]


def test_a_proposal_over_an_existing_draft_says_confirming_replaces_it(
    session: Session, manager: User, employee: User
):
    shift = monday_shift(session, staff=1)
    make_availability(session, shift, employee)
    make_schedule(session, status=ScheduleStatus.draft)

    outcome = propose(session, manager)

    assert outcome.proposal["replaces_draft"] is True
    assert outcome.content["replaces_draft"] is True


def test_a_published_week_cannot_get_a_new_draft(session: Session, manager: User):
    monday_shift(session)
    make_schedule(session, status=ScheduleStatus.published)

    outcome = propose(session, manager)

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "schedule_published"
    assert outcome.proposal is None


def test_the_name_of_a_day_off_is_matched_by_first_name_ignoring_case(
    session: Session, manager: User, employee: User
):
    monday_shift(session)

    outcome = propose(session, manager, unavailable=[{"name": "eli", "day": WEEK}])

    assert outcome.proposal["unavailable"][0]["user_id"] == employee.id


def test_an_unknown_name_is_an_error_listing_the_active_employees(
    session: Session, manager: User, employee: User, other_employee: User
):
    monday_shift(session)

    outcome = propose(session, manager, unavailable=[{"name": "Zed", "day": WEEK}])

    assert outcome.status == "error"
    assert outcome.content["error"] == {
        "code": "user_not_assignable",
        "message": (
            "No active employee is called 'Zed'. Active employees: Dana Other, Eli Employee."
        ),
    }


def test_an_ambiguous_name_asks_which_one(session: Session, manager: User, employee: User):
    make_user(session, name="Eli Second")
    monday_shift(session)

    outcome = propose(session, manager, unavailable=[{"name": "Eli", "day": WEEK}])

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "validation_error"
    assert "Eli Employee, Eli Second" in outcome.content["error"]["message"]


def test_a_full_name_wins_over_a_shared_first_name(session: Session, manager: User, employee: User):
    make_user(session, name="Eli Second")
    monday_shift(session)

    outcome = propose(session, manager, unavailable=[{"name": "Eli Second", "day": WEEK}])

    assert outcome.proposal["unavailable"][0]["name"] == "Eli Second"


def test_a_week_start_that_is_not_a_sunday_is_a_tool_error(session: Session, manager: User):
    outcome = run(session, manager, "generate_schedule_draft", week_start=NEXT_MONDAY.isoformat())

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "invalid_week_start"


def test_a_day_outside_the_week_is_a_tool_error(session: Session, manager: User, employee: User):
    monday_shift(session)

    outcome = propose(session, manager, unavailable=[{"name": "Eli", "day": THIS_WEEK.isoformat()}])

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "validation_error"


def test_a_week_without_shifts_is_a_tool_error(session: Session, manager: User):
    outcome = propose(session, manager)

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "no_shifts_for_week"


def test_generate_schedule_draft_is_refused_for_an_employee_and_writes_nothing(
    session: Session, employee: User
):
    monday_shift(session)

    outcome = run(session, employee, "generate_schedule_draft", week_start=WEEK)

    assert outcome.status == "refused"
    assert saved_rows(session) == (0, 0)


def test_a_manager_role_check_uses_the_database_role_not_the_arguments(
    session: Session, employee: User
):
    outcome = run(session, employee, "generate_schedule_draft", week_start=WEEK, role=Role.manager)

    assert outcome.status == "refused"
