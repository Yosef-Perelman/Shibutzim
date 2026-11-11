from sqlalchemy.orm import Session

from app.models import ToolCallLog


def add(session: Session, log: ToolCallLog) -> None:
    session.add(log)
    session.flush()
