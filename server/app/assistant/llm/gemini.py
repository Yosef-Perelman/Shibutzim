"""The Gemini implementation of `LLM`. The only module that imports the provider's SDK."""

import logging
from collections.abc import Sequence
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from app.assistant.llm.types import (
    ChatResult,
    EmbedTask,
    Message,
    ToolCall,
    ToolDefinition,
)
from app.core.errors import ServiceUnavailable

logger = logging.getLogger("app.assistant.llm")

UNAVAILABLE_MESSAGE = "The assistant is not available right now. Please try again in a moment."
TASK_TYPES = {EmbedTask.document: "RETRIEVAL_DOCUMENT", EmbedTask.query: "RETRIEVAL_QUERY"}
PROVIDER_ERRORS = (errors.APIError, httpx.HTTPError)


class GeminiLLM:
    def __init__(
        self,
        *,
        api_key: str,
        chat_model: str,
        embedding_model: str,
        embedding_dimensions: int,
        timeout_seconds: int,
        client: Any | None = None,
    ) -> None:
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self._client = client or genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=timeout_seconds * 1000)
        )

    def chat(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ChatResult:
        try:
            response = self._client.models.generate_content(
                model=self.chat_model,
                contents=to_contents(messages),
                config=to_config(system, tools),
            )
        except PROVIDER_ERRORS as error:
            raise unavailable(error) from error
        return to_result(response)

    def embed(
        self, texts: Sequence[str], task: EmbedTask = EmbedTask.document
    ) -> list[list[float]]:
        try:
            response = self._client.models.embed_content(
                model=self.embedding_model,
                contents=list(texts),
                config=types.EmbedContentConfig(
                    task_type=TASK_TYPES[task], output_dimensionality=self.embedding_dimensions
                ),
            )
        except PROVIDER_ERRORS as error:
            raise unavailable(error) from error
        vectors = [list(item.values or []) for item in response.embeddings or []]
        if len(vectors) != len(texts):
            raise unavailable(ValueError(f"asked for {len(texts)} embeddings, got {len(vectors)}"))
        return vectors


def unavailable(error: Exception) -> ServiceUnavailable:
    """Log the provider's detail and return the safe error; the message never leaks it."""
    logger.warning("Model provider call failed: %s", error)
    return ServiceUnavailable(message=UNAVAILABLE_MESSAGE)


def to_contents(messages: Sequence[Message]) -> list[types.Content]:
    contents = []
    for message in messages:
        if message.role == "tool":
            parts = [
                types.Part(
                    function_response=types.FunctionResponse(
                        name=result.name, response=result.content
                    )
                )
                for result in message.tool_results
            ]
            contents.append(types.Content(role="user", parts=parts))
            continue
        parts = [types.Part(text=message.text)] if message.text else []
        parts += [
            types.Part(
                function_call=types.FunctionCall(name=call.name, args=call.args),
                thought_signature=call.signature,
            )
            for call in message.tool_calls
        ]
        contents.append(
            types.Content(role="user" if message.role == "user" else "model", parts=parts)
        )
    return contents


def to_config(system: str, tools: Sequence[ToolDefinition]) -> types.GenerateContentConfig:
    declarations = [
        types.FunctionDeclaration(
            name=tool.name, description=tool.description, parameters_json_schema=tool.parameters
        )
        for tool in tools
    ]
    return types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(function_declarations=declarations)] if declarations else None,
        # The agent loop dispatches tools itself, as the current user, and logs each call.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.0,
    )


def to_result(response: types.GenerateContentResponse) -> ChatResult:
    candidates = response.candidates or []
    parts = (candidates[0].content.parts or []) if candidates and candidates[0].content else []
    text = "".join(part.text for part in parts if part.text and not part.thought)
    calls = tuple(
        ToolCall(
            id=part.function_call.id or f"call_{number}",
            name=part.function_call.name or "",
            args=dict(part.function_call.args or {}),
            signature=part.thought_signature,
        )
        for number, part in enumerate((p for p in parts if p.function_call), start=1)
    )
    return ChatResult(text=text, tool_calls=calls)
