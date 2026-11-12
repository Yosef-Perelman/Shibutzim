"""Runs the MCP server over stdio: `uv run python -m app.mcp` (plan 005).

stdout carries the protocol, so everything meant for a person goes to stderr. The token is checked
once before any client connects, so a wrong or expired one is a clear message, not a silent server.
"""

import asyncio
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime

from mcp.server.stdio import stdio_server
from sqlalchemy.orm import Session

from app.assistant.llm.provider import get_llm
from app.config import get_settings
from app.core.errors import DomainError
from app.db import SessionLocal
from app.mcp.server import build_server
from app.services import auth_service

MISSING_TOKEN_MESSAGE = (
    "SHIBUTZIM_MCP_TOKEN is not set. Sign in with POST /api/auth/login and put the access_token "
    "in the environment of this server (see the README)."
)


def now() -> datetime:
    return datetime.now(UTC)


def check_token(
    open_session: Callable[[], AbstractContextManager[Session]], token: str, *, now: datetime
) -> str:
    """Who the token is, e.g. "Dana Levi (manager)"; raises a domain error when it is not valid."""
    with open_session() as session:
        user = auth_service.authenticate_token(session, token, now=now)
        return f"{user.name} ({user.role})"


async def serve(token: str) -> None:
    server = build_server(token=token, open_session=SessionLocal, llm_factory=get_llm, now=now)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> int:
    token = get_settings().shibutzim_mcp_token
    if not token:
        print(MISSING_TOKEN_MESSAGE, file=sys.stderr)
        return 2
    try:
        who = check_token(SessionLocal, token, now=now())
    except DomainError as error:
        print(f"The access token was rejected: {error.message} Sign in again.", file=sys.stderr)
        return 2
    print(f"Shibutzim MCP server running as {who}.", file=sys.stderr)
    asyncio.run(serve(token))
    return 0


if __name__ == "__main__":
    sys.exit(main())
