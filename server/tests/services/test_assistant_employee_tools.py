"""The employee tools run the same services as the UI, as the current user (plan 004)."""

from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy.orm import Session

from app.assistant.context import ToolContext
from app.assistant.dispatch import call_tool
from app.assistant.llm import FakeLLM, basis_vector
from app.core.enums import ScheduleStatus
from app.models import User
from app.services import handbook_service
from app.services.handbook_service import Section
from tests.factories import (
    NEXT_WEEK,
    THIS_WEEK,
    make_assignment,
    make_schedule,
    make_shift,
    make_shift_template,
    make_time_entry,
)

MONDAY = date(2026, 3, 9)  # the Monday of THIS_WEEK
NO_LLM = FakeLLM([])


def run(session: Session, user: User, tool: str, llm=NO_LLM, **args):
    return call_tool(ToolContext(session=session, user=user, llm=llm), tool, args)


def local(day: date, hour: int, minute: int = 0) -> datetime:
    """A UTC instant for local (Asia/Jerusalem, UTC+2 in March) wall-clock time on `day`."""
    return datetime.combine(day, time(hour, minute), tzinfo=UTC) - timedelta(hours=2)


def plan_shift(
    session: Session,
    user: User,
    *,
    name="Morning",
    start=time(7),
    end=time(15),
    weekday=1,
    week=THIS_WEEK,
    status=ScheduleStatus.published,
):
    template = make_shift_template(
        session, name=name, weekday=weekday, start_time=start, end_time=end
    )
    shift = make_shift(session, template, week_start=week)
    schedule = make_schedule(session, week_start=week, status=status) if status else None
    make_assignment(session, schedule, shift, user)
    return shift


# --- get_my_shifts ---


def test_get_my_shifts_lists_the_planned_shifts_with_local_times(session: Session, employee: User):
    plan_shift(session, employee)

    outcome = run(session, employee, "get_my_shifts", **{"from": "2026-03-09", "to": "2026-03-15"})

    assert outcome.status == "ok"
    assert outcome.content == {
        "count": 1,
        "shifts": [
            {
                "date": "2026-03-09",
                "weekday": "Monday",
                "name": "Morning",
                "start": "07:00",
                "end": "15:00",
                "ends_next_day": False,
                "schedule": "published",
            }
        ],
    }


def test_get_my_shifts_marks_a_shift_that_ends_the_next_day(session: Session, employee: User):
    plan_shift(session, employee, name="Night", start=time(23), end=time(7))

    outcome = run(session, employee, "get_my_shifts", **{"from": "2026-03-09", "to": "2026-03-09"})

    shift = outcome.content["shifts"][0]
    assert (shift["start"], shift["end"], shift["ends_next_day"]) == ("23:00", "07:00", True)


def test_get_my_shifts_hides_a_schedule_that_is_not_published(session: Session, employee: User):
    plan_shift(session, employee, week=NEXT_WEEK, status=ScheduleStatus.draft)

    outcome = run(session, employee, "get_my_shifts", **{"from": "2026-03-16", "to": "2026-03-16"})

    assert outcome.content == {"count": 0, "shifts": []}


def test_get_my_shifts_only_returns_shifts_in_the_range(session: Session, employee: User):
    plan_shift(session, employee)

    outcome = run(session, employee, "get_my_shifts", **{"from": "2026-03-10", "to": "2026-03-12"})

    assert outcome.content["count"] == 0


# --- get_my_hours ---


def test_get_my_hours_sums_a_split_shift_into_one_work_day(session: Session, employee: User):
    make_time_entry(session, employee, clock_in=local(MONDAY, 7), duration=timedelta(hours=4))
    make_time_entry(session, employee, clock_in=local(MONDAY, 16), duration=timedelta(hours=6))

    outcome = run(session, employee, "get_my_hours", **{"from": "2026-03-09", "to": "2026-03-09"})

    assert outcome.content == {
        "from": "2026-03-09",
        "to": "2026-03-09",
        "work_days": 1,
        "total_hours": "10.00",
        "regular_hours": "8.00",
        "overtime_hours": "2.00",
        "open_entries": 0,
        "days": [{"date": "2026-03-09", "hours": "10.00", "overtime_hours": "2.00"}],
    }


def test_get_my_hours_counts_an_entry_that_is_still_open_but_not_its_hours(
    session: Session, employee: User
):
    make_time_entry(session, employee, clock_in=local(MONDAY, 7), duration=timedelta(hours=8))
    make_time_entry(session, employee, clock_in=local(MONDAY + timedelta(days=1), 7), duration=None)

    outcome = run(session, employee, "get_my_hours", **{"from": "2026-03-09", "to": "2026-03-10"})

    assert outcome.content["total_hours"] == "8.00"
    assert outcome.content["open_entries"] == 1


def test_get_my_hours_without_entries_is_zero(session: Session, employee: User):
    outcome = run(session, employee, "get_my_hours", **{"from": "2026-03-09", "to": "2026-03-15"})

    assert outcome.content["total_hours"] == "0.00"
    assert outcome.content["days"] == []


# --- explain_pay ---


def test_explain_pay_shows_each_tier_with_its_hours_and_amount(session: Session, employee: User):
    make_time_entry(session, employee, clock_in=local(MONDAY, 7), duration=timedelta(hours=9))

    outcome = run(session, employee, "explain_pay", **{"from": "2026-03-09", "to": "2026-03-09"})

    assert outcome.content == {
        "from": "2026-03-09",
        "to": "2026-03-09",
        "currency": "ILS",
        "hourly_rate": "50.00",
        "total_hours": "9.00",
        "total_amount": "462.50",
        "open_entries": 0,
        "days": [
            {
                "date": "2026-03-09",
                "hours": "9.00",
                "amount": "462.50",
                "tiers": [
                    {"rate_percent": 100, "hours": "8.00", "amount": "400.00"},
                    {"rate_percent": 125, "hours": "1.00", "amount": "62.50"},
                ],
            }
        ],
    }


def test_explain_pay_leaves_out_tiers_the_day_never_reached(session: Session, employee: User):
    make_time_entry(session, employee, clock_in=local(MONDAY, 7), duration=timedelta(hours=5))

    outcome = run(session, employee, "explain_pay", **{"from": "2026-03-09", "to": "2026-03-09"})

    assert outcome.content["days"][0]["tiers"] == [
        {"rate_percent": 100, "hours": "5.00", "amount": "250.00"}
    ]


def test_an_employee_never_sees_anyone_elses_pay_through_the_tool(
    session: Session, employee: User, other_employee: User
):
    make_time_entry(session, other_employee, clock_in=local(MONDAY, 7))

    outcome = run(session, employee, "explain_pay", **{"from": "2026-03-09", "to": "2026-03-09"})

    assert outcome.content["total_hours"] == "0.00"


# --- search_policy ---


def test_search_policy_returns_the_closest_sections_with_titles_to_cite(
    session: Session, employee: User
):
    swaps = Section("Shift swaps", "Ask your manager.")
    breaks = Section("Breaks", "30 minutes after 6 hours.")
    llm = FakeLLM(
        [],
        embeddings={
            handbook_service.embedding_text(swaps): basis_vector(0),
            handbook_service.embedding_text(breaks): basis_vector(1),
            "Can I swap a shift?": basis_vector(0),
        },
    )
    handbook_service.ingest_handbook(session, llm, [swaps, breaks])

    outcome = run(session, employee, "search_policy", llm=llm, query="Can I swap a shift?")

    assert outcome.status == "ok"
    assert outcome.content["matches"][0] == {
        "section_title": "Shift swaps",
        "content": "Ask your manager.",
        "score": 1.0,
    }


def test_search_policy_rejects_an_empty_query_as_a_tool_error(session: Session, employee: User):
    outcome = run(session, employee, "search_policy", query="")

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "validation_error"


@pytest.mark.parametrize("tool", ["get_my_shifts", "get_my_hours", "explain_pay"])
def test_a_range_that_ends_before_it_starts_is_a_tool_error_the_model_can_explain(
    session: Session, employee: User, tool: str
):
    outcome = run(session, employee, tool, **{"from": "2026-03-15", "to": "2026-03-09"})

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "validation_error"
