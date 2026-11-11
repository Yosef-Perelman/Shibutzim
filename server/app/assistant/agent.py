"""The agent loop (architecture §6.4): model, tool call, tool result, model, until a text answer.

The loop only decides what to ask next. Every tool call goes through `call_tool`, which checks the
user's role, runs the tool as that user and logs it, so the model gets exactly the user's access.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from string import Template
from typing import Any

from app.assistant.context import ToolContext, User
from app.assistant.dispatch import call_tool
from app.assistant.llm import Message, ToolResult
from app.assistant.prompts import load_prompt
from app.assistant.tools import registry
from app.core.enums import Role
from app.core.time import DAYS_PER_WEEK, week_start, weekday_sunday_based
from app.scheduler.explain import WEEKDAY_NAMES

EMPTY_ANSWER = "Sorry, I could not come up with an answer. Please try asking in another way."
STEP_LIMIT_ANSWER = "Sorry, I could not finish looking that up. Please try a simpler question."
POLICY_TOOL = "search_policy"


@dataclass(frozen=True)
class ToolCallInfo:
    """What the UI and the evals see of a tool call: its name and arguments, not its result."""

    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class AgentReply:
    text: str
    citations: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    proposal: dict[str, Any] | None = None


def run_agent(
    context: ToolContext, history: Sequence[Message], *, today: date, max_steps: int
) -> AgentReply:
    system = render_system_prompt(context.user, today)
    definitions = registry.definitions_for_role(context.user.role)
    messages = list(history)
    calls: list[ToolCallInfo] = []
    sections: list[str] = []
    proposal: dict[str, Any] | None = None

    for _ in range(max_steps):
        result = context.llm.chat(system, messages, definitions)
        if not result.tool_calls:
            text = result.text.strip() or EMPTY_ANSWER
            return AgentReply(text, cited(text, sections), calls, proposal)
        messages.append(Message.assistant(result.text, result.tool_calls))
        results = []
        for call in result.tool_calls:
            outcome = call_tool(context, call.name, call.args)
            calls.append(ToolCallInfo(call.name, call.args))
            results.append(ToolResult(call.id, call.name, outcome.content))
            proposal = outcome.proposal or proposal
            if call.name == POLICY_TOOL:
                sections += [match["section_title"] for match in outcome.content.get("matches", [])]
        messages.append(Message.tool(tuple(results)))
    return AgentReply(STEP_LIMIT_ANSWER, [], calls, proposal)


def cited(text: str, sections: list[str]) -> list[str]:
    """The handbook sections that were found and that the answer names, once each, in order."""
    lowered = text.casefold()
    found: list[str] = []
    for title in sections:
        if title.casefold() in lowered and title not in found:
            found.append(title)
    return found


def render_system_prompt(user: User, today: date) -> str:
    """The system prompt file with who is asking and what day it is filled in."""
    this_week = week_start(today)
    next_week = this_week + timedelta(days=DAYS_PER_WEEK)
    role_label = "a manager" if user.role is Role.manager else "an employee"
    return Template(load_prompt("system.md")).safe_substitute(
        name=user.name,
        role_label=role_label,
        today_label=label(today),
        this_week_label=label(this_week),
        next_week_label=label(next_week),
        next_week_days=", ".join(label(next_week + timedelta(days=n)) for n in range(7)),
        role_rules=load_prompt(f"role_{user.role.value}.md"),
    )


def label(day: date) -> str:
    """The weekday next to the date, e.g. "Monday 2026-03-09", so the model never works it out."""
    return f"{WEEKDAY_NAMES[weekday_sunday_based(day)]} {day.isoformat()}"
