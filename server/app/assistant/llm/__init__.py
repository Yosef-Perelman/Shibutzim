"""The `llm` interface: one protocol, a Gemini adapter and a scripted fake for tests."""

from app.assistant.llm.fake import FakeLLM, basis_vector, call_tool, say
from app.assistant.llm.gemini import GeminiLLM
from app.assistant.llm.types import (
    LLM,
    ChatResult,
    EmbedTask,
    Message,
    ToolCall,
    ToolDefinition,
    ToolResult,
)

__all__ = [
    "LLM",
    "ChatResult",
    "EmbedTask",
    "FakeLLM",
    "GeminiLLM",
    "Message",
    "ToolCall",
    "ToolDefinition",
    "ToolResult",
    "basis_vector",
    "call_tool",
    "say",
]
