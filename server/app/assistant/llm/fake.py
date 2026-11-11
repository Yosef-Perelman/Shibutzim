"""A scripted model for tests: replays prepared replies and records every call it gets."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.assistant.llm.types import (
    ChatResult,
    EmbedTask,
    Message,
    ToolCall,
    ToolDefinition,
)

DIMENSIONS = 768


def say(text: str) -> ChatResult:
    """A scripted text answer."""
    return ChatResult(text=text)


def call_tool(name: str, **args: Any) -> ChatResult:
    """A scripted request for one tool call."""
    return ChatResult(tool_calls=(ToolCall(id="call_1", name=name, args=args),))


def basis_vector(index: int, dimensions: int = DIMENSIONS) -> list[float]:
    """A unit vector with a single one, so cosine ranking in tests is exact."""
    vector = [0.0] * dimensions
    vector[index] = 1.0
    return vector


@dataclass(frozen=True)
class ChatCall:
    system: str
    messages: tuple[Message, ...]
    tools: tuple[ToolDefinition, ...]


class FakeLLM:
    """Satisfies `LLM`. Running out of scripted replies or embeddings is a test failure."""

    def __init__(
        self,
        replies: Sequence[ChatResult],
        embeddings: Mapping[str, Sequence[float]] | None = None,
    ) -> None:
        self._replies = list(replies)
        self._embeddings = {text: list(vector) for text, vector in (embeddings or {}).items()}
        self.chat_calls: list[ChatCall] = []
        self.embed_calls: list[tuple[tuple[str, ...], EmbedTask]] = []

    def chat(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ChatResult:
        self.chat_calls.append(ChatCall(system, tuple(messages), tuple(tools)))
        if not self._replies:
            raise AssertionError("FakeLLM has no scripted reply left for this chat call.")
        return self._replies.pop(0)

    def embed(
        self, texts: Sequence[str], task: EmbedTask = EmbedTask.document
    ) -> list[list[float]]:
        self.embed_calls.append((tuple(texts), task))
        vectors = []
        for text in texts:
            if text not in self._embeddings:
                raise AssertionError(f"FakeLLM has no scripted embedding for {text!r}.")
            vectors.append(list(self._embeddings[text]))
        return vectors
