"""One chat turn: the history in, the assistant's answer out."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.assistant.agent import AgentReply, run_agent
from app.assistant.context import ToolContext
from app.assistant.llm import LLM, Message
from app.config import get_settings
from app.models import User


def answer(
    session: Session, user: User, llm: LLM, history: Sequence[Message], *, now: datetime
) -> AgentReply:
    """Answer the last user message as `user`. `now` gives the model today's local date."""
    settings = get_settings()
    context = ToolContext(session=session, user=user, llm=llm)
    return run_agent(
        context,
        history,
        today=now.astimezone(settings.tz).date(),
        max_steps=settings.assistant_max_steps,
    )
