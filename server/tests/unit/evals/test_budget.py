"""The budget wrapper that keeps eval runs inside the provider's usage limits."""

import pytest
from evals.budget import BudgetedLLM, BudgetExceeded

from app.assistant.llm import FakeLLM, Message, say


class Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def budgeted(llm: FakeLLM, clock: Clock, *, max_calls: int = 10, interval: float = 5.0):
    return BudgetedLLM(
        llm,
        max_calls=max_calls,
        min_interval_seconds=interval,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )


def test_calls_are_passed_through_and_counted():
    llm = FakeLLM([say("a"), say("b")], embeddings={"q": [1.0]})
    wrapper = budgeted(llm, Clock())

    assert wrapper.chat("s", [Message.user("hi")], []).text == "a"
    assert wrapper.embed(["q"]) == [[1.0]]
    assert wrapper.calls == 2


def test_the_wrapper_waits_so_calls_are_at_least_the_interval_apart():
    clock = Clock()
    wrapper = budgeted(FakeLLM([say("a"), say("b"), say("c")]), clock, interval=5.0)

    wrapper.chat("s", [Message.user("1")], [])
    clock.now += 2  # the model work took two seconds
    wrapper.chat("s", [Message.user("2")], [])
    clock.now += 9  # longer than the interval: no wait needed
    wrapper.chat("s", [Message.user("3")], [])

    assert clock.sleeps == [3.0]


def test_the_first_call_does_not_wait():
    clock = Clock()

    budgeted(FakeLLM([say("a")]), clock).chat("s", [Message.user("1")], [])

    assert clock.sleeps == []


def test_a_call_past_the_budget_raises_before_reaching_the_provider():
    llm = FakeLLM([say("a"), say("b")])
    wrapper = budgeted(llm, Clock(), max_calls=1)
    wrapper.chat("s", [Message.user("1")], [])

    with pytest.raises(BudgetExceeded):
        wrapper.chat("s", [Message.user("2")], [])

    assert len(llm.chat_calls) == 1
