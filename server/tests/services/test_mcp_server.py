"""The MCP server: the assistant's tools for any MCP client, with the assistant's rules (plan 005).

Every test talks to the server through the real MCP client, in memory. No test calls a real model.
"""

import asyncio
import json
from contextlib import nullcontext
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mcp.client import Client
from mcp.types import CallToolResult
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant.llm import LLM, FakeLLM
from app.assistant.tools import registry
from app.core.enums import AvailabilityStatus, Role
from app.core.errors import ServiceUnavailable
from app.core.security import create_access_token
from app.mcp.server import build_server
from app.models import Assignment, Schedule, ToolCallLog, User
from app.services import user_service
from tests.factories import (
    NEXT_WEEK,
    NOW,
    make_availability,
    make_shift,
    make_shift_template,
    make_time_entry,
)
from tests.services.test_assistant_employee_tools import MONDAY, local

WEEK = NEXT_WEEK.isoformat()
MANAGER_ONLY = {"who_is_available", "get_team_hours", "generate_schedule_draft"}
EMPLOYEE_ONLY = {"get_my_shifts", "get_my_hours", "explain_pay"}


def token_of(user: User) -> str:
    return create_access_token(user.id, user.role, now=NOW)


def server_for(session: Session, token: str, llm_factory=lambda: FakeLLM([])):
    return build_server(
        token=token,
        open_session=lambda: nullcontext(session),
        llm_factory=llm_factory,
        now=lambda: NOW,
    )


def list_tools(session: Session, user: User):
    async def go():
        async with Client(server_for(session, token_of(user))) as client:
            return (await client.list_tools()).tools

    return asyncio.run(go())


def call(
    session: Session, user: User, name: str, args: dict[str, Any] | None = None, **server_options
) -> CallToolResult:
    async def go():
        server = server_for(session, server_options.pop("token", token_of(user)), **server_options)
        async with Client(server) as client:
            return await client.call_tool(name, args or {})

    return asyncio.run(go())


def payload(result: CallToolResult) -> dict[str, Any]:
    return json.loads(result.content[0].text)


# --- which tools a token sees ---


def test_a_manager_is_offered_exactly_the_tools_of_the_manager_role(
    session: Session, manager: User
) -> None:
    offered = {tool.name for tool in list_tools(session, manager)}

    assert offered == {tool.name for tool in registry.tools_for_role(Role.manager)}
    assert offered >= MANAGER_ONLY


def test_an_employee_is_offered_exactly_the_tools_of_the_employee_role(
    session: Session, employee: User
) -> None:
    offered = {tool.name for tool in list_tools(session, employee)}

    assert offered == {tool.name for tool in registry.tools_for_role(Role.employee)}
    assert offered >= EMPLOYEE_ONLY
    assert offered.isdisjoint(MANAGER_ONLY)


def test_each_tool_has_the_assistants_description_and_argument_schema(
    session: Session, manager: User
) -> None:
    definitions = {d.name: d for d in registry.definitions_for_role(Role.manager)}

    for tool in list_tools(session, manager):
        assert tool.description == definitions[tool.name].description
        assert tool.inputSchema == definitions[tool.name].parameters
        assert tool.inputSchema["type"] == "object"


# --- a call runs as the token's user ---


def test_a_call_returns_the_tool_result_as_json(session: Session, employee: User) -> None:
    make_time_entry(session, employee, clock_in=local(MONDAY, 7), duration=timedelta(hours=9))

    result = call(session, employee, "get_my_hours", {"from": "2026-03-09", "to": "2026-03-09"})

    assert result.isError is False
    assert payload(result)["total_hours"] == "9.00"
    assert payload(result)["overtime_hours"] == "1.00"
    assert result.structuredContent == payload(result)


def test_get_my_hours_matches_the_pay_endpoint(
    session: Session, employee: User, employee_client: TestClient
) -> None:
    make_time_entry(session, employee, clock_in=local(MONDAY, 7), duration=timedelta(hours=4))
    make_time_entry(session, employee, clock_in=local(MONDAY, 16), duration=timedelta(hours=6))

    pay = employee_client.get("/api/pay", params={"from": "2026-03-09", "to": "2026-03-09"}).json()
    result = call(session, employee, "get_my_hours", {"from": "2026-03-09", "to": "2026-03-09"})

    assert payload(result)["total_hours"] == pay["hours"] == "10.00"


def test_an_employee_gets_only_their_own_hours(
    session: Session, employee: User, other_employee: User
) -> None:
    make_time_entry(session, other_employee, clock_in=local(MONDAY, 7), duration=timedelta(hours=8))

    result = call(session, employee, "get_my_hours", {"from": "2026-03-09", "to": "2026-03-15"})

    assert payload(result)["total_hours"] == "0.00"


def test_a_call_writes_one_tool_call_log_row_for_the_token_user(
    session: Session, employee: User
) -> None:
    call(session, employee, "get_my_hours", {"from": "2026-03-09", "to": "2026-03-15"})

    rows = list(session.scalars(select(ToolCallLog)))
    assert [(row.user_id, row.tool, row.status) for row in rows] == [
        (employee.id, "get_my_hours", "ok")
    ]


# --- refusals and errors are results, not crashes ---


def test_a_manager_tool_called_by_an_employee_is_refused_and_logged(
    session: Session, employee: User
) -> None:
    result = call(session, employee, "get_team_hours", {"from": "2026-03-09", "to": "2026-03-15"})

    assert result.isError is True
    assert payload(result)["error"]["code"] == "forbidden"
    assert [row.status for row in session.scalars(select(ToolCallLog))] == ["refused"]


def test_an_unknown_tool_is_an_error_result(session: Session, employee: User) -> None:
    result = call(session, employee, "delete_everything")

    assert result.isError is True
    assert payload(result)["error"]["code"] == "unknown_tool"


def test_bad_arguments_are_an_error_result_the_client_can_read(
    session: Session, employee: User
) -> None:
    result = call(session, employee, "get_my_hours", {"from": "yesterday", "to": "2026-03-15"})

    assert result.isError is True
    assert payload(result)["error"]["code"] == "validation_error"


def test_a_missing_handbook_model_is_an_error_result_and_not_a_crash(
    session: Session, employee: User
) -> None:
    def unavailable() -> LLM:
        raise ServiceUnavailable(message="The assistant is not available right now.")

    result = call(
        session, employee, "search_policy", {"query": "overtime"}, llm_factory=unavailable
    )

    assert result.isError is True
    assert "not available" in payload(result)["error"]["message"]


# --- writes are proposals ---


def test_a_schedule_draft_is_returned_as_a_proposal_and_saves_nothing(
    session: Session, manager: User, employee: User
) -> None:
    template = make_shift_template(session, required_staff=1)
    shift = make_shift(session, template, week_start=NEXT_WEEK)
    make_availability(session, shift, employee, AvailabilityStatus.preferred)

    result = call(session, manager, "generate_schedule_draft", {"week_start": WEEK})

    assert result.isError is False
    proposal = payload(result)["proposal"]
    assert proposal["type"] == "schedule_draft"
    assert proposal["week_start"] == WEEK
    assert session.query(Schedule).count() == 0
    assert session.query(Assignment).count() == 0


# --- the token ---


def test_a_garbage_token_is_an_error_result_for_a_call(session: Session) -> None:
    async def go():
        async with Client(server_for(session, "not-a-token")) as client:
            return await client.call_tool(
                "get_my_hours", {"from": "2026-03-09", "to": "2026-03-09"}
            )

    result = asyncio.run(go())

    assert result.isError is True
    assert payload(result)["error"]["code"] == "invalid_token"


def test_a_garbage_token_cannot_list_tools(session: Session) -> None:
    async def go():
        async with Client(server_for(session, "not-a-token")) as client:
            return await client.list_tools()

    with pytest.raises(Exception, match="Invalid authentication token"):
        asyncio.run(go())


def test_deactivating_the_user_cuts_the_token_off_on_the_next_call(
    session: Session, manager: User, employee: User
) -> None:
    before = call(session, employee, "get_my_hours", {"from": "2026-03-09", "to": "2026-03-09"})
    user_service.set_user_active(session, manager, employee.id, is_active=False)
    after = call(session, employee, "get_my_hours", {"from": "2026-03-09", "to": "2026-03-09"})

    assert before.isError is False
    assert after.isError is True
    assert payload(after)["error"]["code"] == "invalid_token"
