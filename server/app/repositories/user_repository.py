from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def get_by_email(session: Session, email: str) -> User | None:
    """`email` must already be normalized (stripped, lowercase) – emails are stored lowercase."""
    return session.scalar(select(User).where(User.email == email))
