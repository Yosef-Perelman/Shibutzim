"""What a tool call runs with: the database session, the current user and the model adapter."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.assistant.llm import LLM
from app.models import User

__all__ = ["ToolContext", "User"]  # User is re-exported so the agent needs no model import


@dataclass(frozen=True)
class ToolContext:
    """Tools call services with `user`, so they inherit exactly the UI's authorization."""

    session: Session
    user: User
    llm: LLM
