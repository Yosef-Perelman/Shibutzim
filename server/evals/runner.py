"""Runs eval cases through the real agent loop and checks each run."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant.agent import run_agent
from app.assistant.context import ToolContext
from app.assistant.llm import LLM, ChatResult, EmbedTask, Message, ToolDefinition
from app.config import get_settings
from app.core.errors import ServiceUnavailable
from app.models import User
from evals.budget import BudgetExceeded
from evals.checks import ToolResults, check_case
from evals.types import EvalCase

PROVIDER_DOWN = "the model provider was not available; the run was stopped"
BUDGET_USED_UP = "the call budget was used up; the run was stopped"


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    passed: bool
    failures: list[str]
    tools: list[str]
    answer: str


class RecordingLLM:
    """Remembers the messages of the last chat call, which hold every tool result of the run."""

    def __init__(self, llm: LLM) -> None:
        self._llm = llm
        self.last_messages: list[Message] = []

    def chat(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ChatResult:
        self.last_messages = list(messages)
        return self._llm.chat(system, messages, tools)

    def embed(
        self, texts: Sequence[str], task: EmbedTask = EmbedTask.document
    ) -> list[list[float]]:
        return self._llm.embed(texts, task)


def run_cases(
    session: Session,
    llm: LLM,
    cases: Sequence[EvalCase],
    *,
    today: date,
    retries: int = 0,
    on_result: Callable[[CaseResult], None] | None = None,
) -> list[CaseResult]:
    """Run each case. A failing case is retried up to `retries` times (behavior only); a provider
    outage or an exhausted budget stops the whole run so no more calls are spent."""
    results: list[CaseResult] = []
    for case in cases:
        result, stop = run_with_retries(session, llm, case, today, retries)
        results.append(result)
        if on_result:
            on_result(result)
        if stop:
            break
    return results


def run_with_retries(
    session: Session, llm: LLM, case: EvalCase, today: date, retries: int
) -> tuple[CaseResult, bool]:
    for _ in range(retries + 1):
        result, stop = run_case(session, llm, case, today)
        if result.passed or stop:
            return result, stop
    return result, False


def run_case(session: Session, llm: LLM, case: EvalCase, today: date) -> tuple[CaseResult, bool]:
    user = session.scalar(select(User).where(User.name == case.persona))
    if user is None:
        message = f"no user named {case.persona}; run scripts/seed.py first"
        return CaseResult(case.id, False, [message], [], ""), False
    recorder = RecordingLLM(llm)
    context = ToolContext(session=session, user=user, llm=recorder)
    try:
        reply = run_agent(
            context,
            [Message.user(case.question)],
            today=today,
            max_steps=get_settings().assistant_max_steps,
        )
    except ServiceUnavailable:
        return CaseResult(case.id, False, [PROVIDER_DOWN], [], ""), True
    except BudgetExceeded:
        return CaseResult(case.id, False, [BUDGET_USED_UP], [], ""), True
    failures = check_case(case, reply, tool_results(recorder.last_messages))
    tools = [call.name for call in reply.tool_calls]
    return CaseResult(case.id, not failures, failures, tools, reply.text), False


def tool_results(messages: Sequence[Message]) -> ToolResults:
    """Every tool result in the conversation, by tool name, in the order the tools ran."""
    found: ToolResults = {}
    for message in messages:
        for result in message.tool_results:
            found.setdefault(result.name, []).append(result.content)
    return found
