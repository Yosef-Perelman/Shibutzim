"""The eval runner drives the agent for each case and checks the run (no real model here)."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.assistant.llm import FakeLLM, call_tool, say
from app.core.errors import ServiceUnavailable
from app.models import User
from evals.budget import BudgetExceeded
from evals.runner import CaseResult, run_cases
from evals.types import EvalCase, Fact

TODAY = date(2026, 3, 9)
HOURS = {"from": "2026-03-01", "to": "2026-03-31"}


def hours_case(**overrides) -> EvalCase:
    base = dict(
        id="hours",
        persona="Eli Employee",
        question="How many hours did I work in March?",
        expected_tools=("get_my_hours",),
        facts=(Fact("get_my_hours", "total_hours"),),
    )
    return EvalCase(**{**base, **overrides})


def test_a_passing_case_reports_its_tools_and_no_failures(session: Session, employee: User):
    llm = FakeLLM([call_tool("get_my_hours", **HOURS), say("You worked 0 hours in March.")])

    [result] = run_cases(session, llm, [hours_case()], today=TODAY)

    assert result == CaseResult(
        case_id="hours",
        passed=True,
        failures=[],
        tools=["get_my_hours"],
        answer="You worked 0 hours in March.",
    )


def test_a_failing_case_lists_why(session: Session, employee: User):
    llm = FakeLLM([call_tool("get_my_hours", **HOURS), say("You worked 40 hours.")])

    [result] = run_cases(session, llm, [hours_case()], today=TODAY)

    assert not result.passed
    assert result.failures == ["the answer does not say get_my_hours.total_hours = 0.00"]


def test_the_case_runs_as_the_named_persona_with_that_users_tools(
    session: Session, employee: User, manager: User
):
    llm = FakeLLM([say("ok"), say("ok")])
    cases = [
        hours_case(id="employee", expected_tools=(), facts=()),
        hours_case(id="manager", persona="Mia Manager", expected_tools=(), facts=()),
    ]

    run_cases(session, llm, cases, today=TODAY)

    employee_tools = {tool.name for tool in llm.chat_calls[0].tools}
    manager_tools = {tool.name for tool in llm.chat_calls[1].tools}
    assert "get_my_hours" in employee_tools and "get_team_hours" not in employee_tools
    assert "get_team_hours" in manager_tools and "get_my_hours" not in manager_tools


def test_an_unknown_persona_is_reported_as_a_failure_without_stopping_the_run(
    session: Session, employee: User
):
    llm = FakeLLM([say("ok")])
    cases = [
        hours_case(id="ghost", persona="Nobody Here"),
        hours_case(id="real", expected_tools=(), facts=()),
    ]

    results = run_cases(session, llm, cases, today=TODAY)

    assert [(r.case_id, r.passed) for r in results] == [("ghost", False), ("real", True)]
    assert results[0].failures == ["no user named Nobody Here; run scripts/seed.py first"]


def test_a_provider_outage_stops_the_run_so_no_more_calls_are_spent(
    session: Session, employee: User
):
    class Down(FakeLLM):
        def chat(self, system, messages, tools):
            raise ServiceUnavailable(message="down")

    cases = [hours_case(id="one"), hours_case(id="two")]

    results = run_cases(session, Down([]), cases, today=TODAY)

    assert [r.case_id for r in results] == ["one"]
    assert results[0].failures == ["the model provider was not available; the run was stopped"]


def test_an_exhausted_budget_stops_the_run(session: Session, employee: User):
    class OutOfBudget(FakeLLM):
        def chat(self, system, messages, tools):
            raise BudgetExceeded("limit reached")

    results = run_cases(
        session, OutOfBudget([]), [hours_case(id="one"), hours_case(id="two")], today=TODAY
    )

    assert [r.case_id for r in results] == ["one"]
    assert results[0].failures == ["the call budget was used up; the run was stopped"]


def test_a_failing_case_is_retried_only_when_asked(session: Session, employee: User):
    script = [call_tool("get_my_hours", **HOURS), say("40 hours")]
    retry_script = [call_tool("get_my_hours", **HOURS), say("You worked 0 hours.")]

    without = FakeLLM(script)
    run_cases(session, without, [hours_case()], today=TODAY, retries=0)
    with_retry = FakeLLM(script + retry_script)
    [result] = run_cases(session, with_retry, [hours_case()], today=TODAY, retries=1)

    assert len(without.chat_calls) == 2
    assert len(with_retry.chat_calls) == 4
    assert result.passed


def test_a_passing_case_is_not_retried(session: Session, employee: User):
    llm = FakeLLM([call_tool("get_my_hours", **HOURS), say("0 hours")])

    run_cases(session, llm, [hours_case()], today=TODAY, retries=3)

    assert len(llm.chat_calls) == 2


@pytest.mark.parametrize("persona", ["Eli Employee"])
def test_the_runs_tool_calls_are_logged_like_real_ones(
    session: Session, employee: User, persona: str
):
    llm = FakeLLM([call_tool("get_my_hours", **HOURS), say("0 hours")])

    run_cases(session, llm, [hours_case(persona=persona)], today=TODAY)

    from sqlalchemy import select

    from app.models import ToolCallLog

    assert session.scalars(select(ToolCallLog.tool)).all() == ["get_my_hours"]
