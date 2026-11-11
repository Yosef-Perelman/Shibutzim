"""The agent loop: model, tool call, tool result, model, until a text answer (§6.4)."""

from datetime import date, time

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant.agent import (
    EMPTY_ANSWER,
    STEP_LIMIT_ANSWER,
    ToolCallInfo,
    render_system_prompt,
    run_agent,
)
from app.assistant.context import ToolContext
from app.assistant.llm import (
    ChatResult,
    FakeLLM,
    Message,
    ToolCall,
    ToolResult,
    basis_vector,
    call_tool,
    say,
)
from app.core.errors import ServiceUnavailable
from app.models import ToolCallLog, User
from app.services import handbook_service
from app.services.handbook_service import Section
from tests.factories import (
    NEXT_WEEK,
    make_availability,
    make_shift,
    make_shift_template,
)

TODAY = date(2026, 3, 9)  # a Monday; next week starts on Sunday 2026-03-15
HOURS = {"from": "2026-03-01", "to": "2026-03-31"}


def agent(session: Session, user: User, llm: FakeLLM, *history: str, max_steps: int = 6):
    messages = [Message.user(text) for text in history] or [Message.user("hi")]
    context = ToolContext(session=session, user=user, llm=llm)
    return run_agent(context, messages, today=TODAY, max_steps=max_steps)


def tool_names(llm: FakeLLM, call: int = 0) -> set[str]:
    return {tool.name for tool in llm.chat_calls[call].tools}


# --- the plain answer ---


def test_a_question_that_needs_no_tool_is_answered_with_the_models_text(
    session: Session, employee: User
):
    llm = FakeLLM([say("Hello Eli!")])

    reply = agent(session, employee, llm, "hi")

    assert reply.text == "Hello Eli!"
    assert reply.tool_calls == []
    assert reply.citations == []
    assert reply.proposal is None
    assert len(llm.chat_calls) == 1


def test_the_model_gets_the_history_and_only_the_tools_of_the_users_role(
    session: Session, employee: User, manager: User
):
    llm = FakeLLM([say("ok"), say("ok")])

    agent(session, employee, llm, "first question", "second question")
    agent(session, manager, llm, "hi")

    assert [m.text for m in llm.chat_calls[0].messages] == ["first question", "second question"]
    assert tool_names(llm, 0) == {"get_my_shifts", "get_my_hours", "explain_pay", "search_policy"}
    assert tool_names(llm, 1) == {
        "who_is_available",
        "get_team_hours",
        "generate_schedule_draft",
        "search_policy",
    }


def test_an_empty_model_answer_becomes_a_polite_fallback(session: Session, employee: User):
    reply = agent(session, employee, FakeLLM([say("   ")]))

    assert reply.text == EMPTY_ANSWER


# --- tools ---


def test_a_tool_call_is_run_as_the_user_and_its_result_goes_back_to_the_model(
    session: Session, employee: User
):
    llm = FakeLLM([call_tool("get_my_hours", **HOURS), say("You worked 0 hours in March.")])

    reply = agent(session, employee, llm, "How many hours in March?")

    assert reply.text == "You worked 0 hours in March."
    assert reply.tool_calls == [ToolCallInfo("get_my_hours", HOURS)]
    second = llm.chat_calls[1].messages
    assert [m.role for m in second] == ["user", "assistant", "tool"]
    assert second[1].tool_calls == (ToolCall("call_1", "get_my_hours", HOURS),)
    [result] = second[2].tool_results
    assert (result.call_id, result.name) == ("call_1", "get_my_hours")
    assert result.content["total_hours"] == "0.00"
    log = session.scalars(select(ToolCallLog)).one()
    assert (log.user_id, log.tool, log.status) == (employee.id, "get_my_hours", "ok")


def test_several_tool_calls_in_one_reply_are_answered_in_one_tool_message(
    session: Session, employee: User
):
    two_calls = ChatResult(
        tool_calls=(
            ToolCall("a", "get_my_hours", HOURS),
            ToolCall("b", "explain_pay", HOURS),
        )
    )
    llm = FakeLLM([two_calls, say("done")])

    reply = agent(session, employee, llm)

    [message] = [m for m in llm.chat_calls[1].messages if m.role == "tool"]
    assert [(r.call_id, r.name) for r in message.tool_results] == [
        ("a", "get_my_hours"),
        ("b", "explain_pay"),
    ]
    assert [info.name for info in reply.tool_calls] == ["get_my_hours", "explain_pay"]


def test_an_unknown_tool_is_refused_and_the_model_can_still_answer(
    session: Session, employee: User
):
    llm = FakeLLM([call_tool("delete_everything"), say("I can't do that.")])

    reply = agent(session, employee, llm)

    [result] = llm.chat_calls[1].messages[-1].tool_results
    assert result.content["error"]["code"] == "unknown_tool"
    assert reply.text == "I can't do that."


def test_a_manager_tool_asked_by_an_employee_is_refused_in_the_tool_layer(
    session: Session, employee: User
):
    llm = FakeLLM([call_tool("get_team_hours", **HOURS), say("Not allowed.")])

    agent(session, employee, llm)

    [result] = llm.chat_calls[1].messages[-1].tool_results
    assert result.content["error"]["code"] == "forbidden"


# --- the step limit ---


def test_a_model_that_keeps_calling_tools_is_stopped_at_the_step_limit(
    session: Session, employee: User
):
    llm = FakeLLM([call_tool("get_my_hours", **HOURS) for _ in range(5)])

    reply = agent(session, employee, llm, max_steps=3)

    assert reply.text == STEP_LIMIT_ANSWER
    assert len(llm.chat_calls) == 3
    assert len(reply.tool_calls) == 3


def test_a_provider_outage_is_not_swallowed(session: Session, employee: User):
    class Down(FakeLLM):
        def chat(self, system, messages, tools):
            raise ServiceUnavailable(message="down")

    with pytest.raises(ServiceUnavailable):
        agent(session, employee, Down([]))


# --- citations ---


def ingest_swaps_and_breaks(session: Session) -> FakeLLM:
    swaps = Section("Shift swaps", "Ask your manager.")
    breaks = Section("Breaks", "30 minutes after 6 hours.")
    embeddings = {
        handbook_service.embedding_text(swaps): basis_vector(0),
        handbook_service.embedding_text(breaks): basis_vector(1),
        "swap a shift": basis_vector(0),
    }
    loader = FakeLLM([], embeddings=embeddings)
    handbook_service.ingest_handbook(session, loader, [swaps, breaks])
    return embeddings


def test_the_sections_the_answer_names_are_the_citations(session: Session, employee: User):
    embeddings = ingest_swaps_and_breaks(session)
    llm = FakeLLM(
        [
            call_tool("search_policy", query="swap a shift"),
            say("According to the Shift swaps section, ask your manager."),
        ],
        embeddings=embeddings,
    )

    reply = agent(session, employee, llm, "Can I swap a shift?")

    assert reply.citations == ["Shift swaps"]


def test_sections_that_were_found_but_not_named_are_not_citations(session: Session, employee: User):
    embeddings = ingest_swaps_and_breaks(session)
    llm = FakeLLM(
        [call_tool("search_policy", query="swap a shift"), say("Ask your manager.")],
        embeddings=embeddings,
    )

    reply = agent(session, employee, llm, "Can I swap a shift?")

    assert reply.citations == []


# --- proposals ---


def test_a_proposal_reaches_the_reply_but_not_the_model(
    session: Session, manager: User, employee: User
):
    template = make_shift_template(session, weekday=1, start_time=time(7), end_time=time(15))
    shift = make_shift(session, template, week_start=NEXT_WEEK, required_staff=1)
    make_availability(session, shift, employee)
    llm = FakeLLM(
        [
            call_tool("generate_schedule_draft", week_start=NEXT_WEEK.isoformat()),
            say("I prepared a proposal. Please confirm it."),
        ]
    )

    reply = agent(session, manager, llm, "Build next week's schedule")

    assert reply.proposal["type"] == "schedule_draft"
    assert reply.proposal["week_start"] == "2026-03-15"
    [result] = llm.chat_calls[1].messages[-1].tool_results
    assert "proposal" not in result.content
    assert "assignments" not in result.content


# --- the system prompt ---


def test_the_system_prompt_tells_the_model_who_and_when(session: Session, employee: User):
    prompt = render_system_prompt(employee, TODAY)

    assert "Eli Employee" in prompt
    assert "Monday 2026-03-09" in prompt
    assert "Sunday 2026-03-15" in prompt  # next week starts here
    assert "Tuesday 2026-03-17" in prompt
    assert "$" not in prompt  # every placeholder was filled


def test_the_system_prompt_has_the_rules_of_the_users_role(
    session: Session, employee: User, manager: User
):
    assert "an employee" in render_system_prompt(employee, TODAY)
    assert "a manager" in render_system_prompt(manager, TODAY)
    assert "generate_schedule_draft" in render_system_prompt(manager, TODAY)
    assert "generate_schedule_draft" not in render_system_prompt(employee, TODAY)


def test_the_system_prompt_forbids_arithmetic_and_requires_citations(
    session: Session, employee: User
):
    prompt = render_system_prompt(employee, TODAY).lower()

    assert "never calculate" in prompt
    assert "section title" in prompt


def test_the_tool_messages_are_plain_data(session: Session, employee: User):
    llm = FakeLLM([call_tool("get_my_hours", **HOURS), say("ok")])

    agent(session, employee, llm)

    [result] = llm.chat_calls[1].messages[-1].tool_results
    assert isinstance(result, ToolResult)
    assert isinstance(result.content, dict)
