"""Dispatching a tool call: role filter, argument validation, error results, and the log."""

import json
from dataclasses import dataclass
from datetime import date

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant.context import ToolContext
from app.assistant.dispatch import call_tool
from app.assistant.llm import FakeLLM
from app.assistant.tools import registry
from app.assistant.tools.base import Tool
from app.core.enums import Role
from app.core.errors import ServiceUnavailable
from app.models import ToolCallLog, User

RANGE = {"from": "2026-03-09", "to": "2026-03-15"}


class NoArguments(BaseModel):
    pass


def context(session: Session, user: User, llm=None) -> ToolContext:
    return ToolContext(session=session, user=user, llm=llm or FakeLLM([]))


def logs(session: Session) -> list[ToolCallLog]:
    return list(session.scalars(select(ToolCallLog).order_by(ToolCallLog.id)))


@dataclass
class Spy:
    calls: int = 0

    def run(self, ctx: ToolContext, arguments: NoArguments) -> dict:
        self.calls += 1
        return {"ok": True}


def install(monkeypatch: pytest.MonkeyPatch, name: str, run, roles=frozenset({Role.employee})):
    tool = Tool(name=name, roles=roles, writes=False, arguments=NoArguments, run=run)
    monkeypatch.setattr(registry, "ALL_TOOLS", (*registry.ALL_TOOLS, tool))


# --- the log ---


def test_every_call_writes_one_log_row_with_its_arguments_and_result_size(
    session: Session, employee: User
):
    outcome = call_tool(context(session, employee), "get_my_hours", RANGE)

    [row] = logs(session)
    assert (row.user_id, row.tool, row.status) == (employee.id, "get_my_hours", "ok")
    assert row.args == RANGE
    assert row.result_size == len(json.dumps(outcome.content, ensure_ascii=False))
    assert row.duration_ms >= 0
    assert isinstance(row.duration_ms, int)


def test_a_failed_call_is_logged_too(session: Session, employee: User):
    call_tool(
        context(session, employee), "get_my_hours", {"from": "2026-03-15", "to": "2026-03-09"}
    )

    [row] = logs(session)
    assert (row.tool, row.status) == ("get_my_hours", "error")


def test_the_log_is_committed_not_left_pending(session: Session, employee: User):
    call_tool(context(session, employee), "get_my_hours", RANGE)

    assert not session.new and not session.dirty


# --- refusals ---


def test_an_unknown_tool_is_refused_and_logged(session: Session, employee: User):
    outcome = call_tool(context(session, employee), "drop_database", {"table": "users"})

    assert outcome.status == "refused"
    assert outcome.content["error"]["code"] == "unknown_tool"
    assert [(row.tool, row.status) for row in logs(session)] == [("drop_database", "refused")]


def test_a_tool_outside_the_users_role_is_refused_without_running(
    monkeypatch: pytest.MonkeyPatch, session: Session, employee: User
):
    spy = Spy()
    install(monkeypatch, "manager_secret", spy.run, roles=frozenset({Role.manager}))

    outcome = call_tool(context(session, employee), "manager_secret", {})

    assert outcome.status == "refused"
    assert outcome.content["error"]["code"] == "forbidden"
    assert spy.calls == 0
    assert [(row.tool, row.status) for row in logs(session)] == [("manager_secret", "refused")]


def test_a_manager_may_run_a_manager_tool(
    monkeypatch: pytest.MonkeyPatch, session: Session, manager: User
):
    spy = Spy()
    install(monkeypatch, "manager_secret", spy.run, roles=frozenset({Role.manager}))

    outcome = call_tool(context(session, manager), "manager_secret", {})

    assert outcome.status == "ok"
    assert outcome.content == {"ok": True}
    assert spy.calls == 1


def test_definitions_for_a_role_hide_the_tools_of_another_role(
    monkeypatch: pytest.MonkeyPatch, employee: User
):
    install(monkeypatch, "manager_secret", Spy().run, roles=frozenset({Role.manager}))

    names = {definition.name for definition in registry.definitions_for_role(Role.employee)}

    assert "manager_secret" not in names


# --- errors become results ---


def test_bad_arguments_come_back_as_a_validation_error_naming_the_field(
    session: Session, employee: User
):
    outcome = call_tool(context(session, employee), "get_my_hours", {"from": "2026-03-09"})

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "validation_error"
    assert "to" in outcome.content["error"]["message"]


def test_a_malformed_date_is_a_validation_error_not_a_crash(session: Session, employee: User):
    outcome = call_tool(
        context(session, employee), "get_my_hours", {"from": "next tuesday", "to": "2026-03-15"}
    )

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "validation_error"


def test_a_domain_error_keeps_its_code_and_message(session: Session, employee: User):
    outcome = call_tool(
        context(session, employee), "get_my_hours", {"from": "2026-03-15", "to": "2026-03-09"}
    )

    assert outcome.content == {
        "error": {"code": "validation_error", "message": "'from' must not be after 'to'."}
    }


def test_an_unexpected_exception_becomes_a_generic_error_result_and_is_logged(
    monkeypatch: pytest.MonkeyPatch, session: Session, employee: User
):
    def explode(ctx: ToolContext, arguments: NoArguments) -> dict:
        raise RuntimeError("secret internals")

    install(monkeypatch, "exploding", explode)
    session.commit()  # what the failure path rolls back to

    outcome = call_tool(context(session, employee), "exploding", {})

    assert outcome.status == "error"
    assert outcome.content["error"]["code"] == "internal_error"
    assert "secret" not in json.dumps(outcome.content)
    assert [(row.tool, row.status) for row in logs(session)] == [("exploding", "error")]


class DownLLM:
    def chat(self, system, messages, tools):
        raise ServiceUnavailable(message="down")

    def embed(self, texts, task=None):
        raise ServiceUnavailable(message="down")


def test_a_provider_outage_is_logged_and_raised_so_the_endpoint_can_answer_503(
    session: Session, employee: User
):
    with pytest.raises(ServiceUnavailable):
        call_tool(context(session, employee, DownLLM()), "search_policy", {"query": "breaks?"})

    assert [(row.tool, row.status) for row in logs(session)] == [("search_policy", "error")]


def test_the_date_arguments_arrive_as_dates(
    monkeypatch: pytest.MonkeyPatch, session: Session, employee: User
):
    seen = {}

    class Dates(BaseModel):
        day: date

    def run(ctx: ToolContext, arguments: Dates) -> dict:
        seen["day"] = arguments.day
        return {}

    tool = Tool(
        name="dates", roles=frozenset({Role.employee}), writes=False, arguments=Dates, run=run
    )
    monkeypatch.setattr(registry, "ALL_TOOLS", (*registry.ALL_TOOLS, tool))

    call_tool(context(session, employee), "dates", {"day": "2026-03-09"})

    assert seen["day"] == date(2026, 3, 9)
