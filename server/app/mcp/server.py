"""The MCP server: the assistant's tools for any MCP client (plan 005, architecture §2 and §10).

It is a third entry point over the same services, like the REST routers and the in-app assistant.
It acts as the user behind one access token. The token is checked again on every request, so
deactivating the user cuts a running server off at once. Every call goes through
`dispatch.call_tool`, so the role filter, argument validation, domain errors and the
`tool_call_logs` row are exactly what the chat has. A write tool returns its proposal and never
writes.
"""

import asyncio
import json
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.lowlevel.server import ServerRequestContext
from mcp.shared.exceptions import INVALID_REQUEST, MCPError
from sqlalchemy.orm import Session

from app.assistant import dispatch
from app.assistant.context import ToolContext
from app.assistant.llm import LLM, ChatResult, EmbedTask, Message, ToolDefinition
from app.assistant.tools import registry
from app.core.errors import DomainError, error_body
from app.services import auth_service

SERVER_NAME = "shibutzim"
SERVER_INSTRUCTIONS = (
    "Shibutzim: shifts, hours, pay and company policy for a small team. The tools act as the "
    "signed-in user and see only what that user may see. A schedule proposal is never saved; "
    "tell the user to confirm it in the app."
)

SessionOpener = Callable[[], AbstractContextManager[Session]]


class LazyLLM:
    """Builds the model adapter on first use, so tools that need no model work without a key."""

    def __init__(self, factory: Callable[[], LLM]) -> None:
        self._factory = factory
        self._llm: LLM | None = None

    def _get(self) -> LLM:
        if self._llm is None:
            self._llm = self._factory()
        return self._llm

    def chat(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> ChatResult:
        return self._get().chat(system, messages, tools)

    def embed(
        self, texts: Sequence[str], task: EmbedTask = EmbedTask.document
    ) -> list[list[float]]:
        return self._get().embed(texts, task)


def build_server(
    *,
    token: str,
    open_session: SessionOpener,
    llm_factory: Callable[[], LLM],
    now: Callable[[], datetime],
) -> Server:
    """A server whose every request runs as the user `token` belongs to."""

    def list_tools_sync() -> list[types.Tool]:
        with open_session() as session:
            user = auth_service.authenticate_token(session, token, now=now())
            return [
                types.Tool(
                    name=definition.name,
                    description=definition.description,
                    inputSchema=definition.parameters,
                )
                for definition in registry.definitions_for_role(user.role)
            ]

    def call_tool_sync(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        with open_session() as session:
            try:
                user = auth_service.authenticate_token(session, token, now=now())
                context = ToolContext(session=session, user=user, llm=LazyLLM(llm_factory))
                outcome = dispatch.call_tool(context, name, arguments)
            except DomainError as error:
                return error_result(error)
        content = outcome.content
        if outcome.proposal is not None:
            content = {**content, "proposal": outcome.proposal}
        return result_of(content, is_error=outcome.status != "ok")

    async def on_list_tools(
        ctx: ServerRequestContext, params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        try:
            tools = await asyncio.to_thread(list_tools_sync)
        except DomainError as error:
            raise MCPError(INVALID_REQUEST, error.message) from error
        return types.ListToolsResult(tools=tools)

    async def on_call_tool(
        ctx: ServerRequestContext, params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        return await asyncio.to_thread(call_tool_sync, params.name, params.arguments or {})

    return Server(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def result_of(content: dict[str, Any], *, is_error: bool) -> types.CallToolResult:
    """The tool's content as JSON text for the model, and again as structured content."""
    text = json.dumps(content, ensure_ascii=False)
    return types.CallToolResult(
        content=[types.TextContent(text=text)],
        structuredContent=content,
        isError=is_error,
    )


def error_result(error: DomainError) -> types.CallToolResult:
    """A refusal the client can read: a rejected token, or a model provider that is not there."""
    return result_of(error_body(error.code, error.message), is_error=True)
