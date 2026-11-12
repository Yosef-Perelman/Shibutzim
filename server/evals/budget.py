"""Keeps a run inside the provider's usage limits: a cap on calls and a gap between them."""

import time
from collections.abc import Callable, Sequence

from app.assistant.llm import LLM, ChatResult, EmbedTask, Message, ToolDefinition


class BudgetExceeded(Exception):
    """The run used all the model calls it was allowed."""


class BudgetedLLM:
    """Wraps an `LLM`: counts every call, refuses past `max_calls`, spaces calls apart."""

    def __init__(
        self,
        llm: LLM,
        *,
        max_calls: int,
        min_interval_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._llm = llm
        self._max_calls = max_calls
        self._interval = min_interval_seconds
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_started: float | None = None
        self.calls = 0

    def chat(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ChatResult:
        self._begin()
        return self._llm.chat(system, messages, tools)

    def embed(
        self, texts: Sequence[str], task: EmbedTask = EmbedTask.document
    ) -> list[list[float]]:
        self._begin()
        return self._llm.embed(texts, task)

    def _begin(self) -> None:
        if self.calls >= self._max_calls:
            raise BudgetExceeded(f"the limit of {self._max_calls} model calls was reached")
        if self._last_started is not None:
            wait = self._interval - (self._monotonic() - self._last_started)
            if wait > 0:
                self._sleep(wait)
        self._last_started = self._monotonic()
        self.calls += 1
