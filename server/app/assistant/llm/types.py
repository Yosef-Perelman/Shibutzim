"""Plain data the `llm` interface takes and returns. No vendor types leak out of the adapter."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, Protocol


class EmbedTask(StrEnum):
    """What an embedding is for; providers embed a question differently from a document."""

    document = "document"
    query = "query"


@dataclass(frozen=True)
class ToolDefinition:
    """One tool the model may call. `parameters` is a JSON schema of the arguments."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """The model asking for a tool. `signature` is an opaque provider token to send back as is."""

    id: str
    name: str
    args: dict[str, Any]
    signature: bytes | None = None


@dataclass(frozen=True)
class ToolResult:
    """What a tool returned, addressed to the call it answers."""

    call_id: str
    name: str
    content: dict[str, Any]


@dataclass(frozen=True)
class Message:
    """One turn of the conversation: a user text, an assistant reply or tool results."""

    role: Literal["user", "assistant", "tool"]
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()

    @classmethod
    def user(cls, text: str) -> "Message":
        return cls(role="user", text=text)

    @classmethod
    def assistant(cls, text: str = "", tool_calls: tuple[ToolCall, ...] = ()) -> "Message":
        return cls(role="assistant", text=text, tool_calls=tool_calls)

    @classmethod
    def tool(cls, results: tuple[ToolResult, ...]) -> "Message":
        return cls(role="tool", tool_results=results)


@dataclass(frozen=True)
class ChatResult:
    """The model's answer to one chat call: text, tool calls, or both."""

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


class LLM(Protocol):
    """The only door to a model provider (architecture §2). Failures are `ServiceUnavailable`."""

    def chat(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ChatResult: ...

    def embed(
        self, texts: Sequence[str], task: EmbedTask = EmbedTask.document
    ) -> list[list[float]]: ...
