"""FastAPI dependencies shared by routers: DB session, clock, current user.

Routers import the `Annotated` aliases below instead of models or SQLAlchemy (coding-rules, layers).
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode, Unauthorized
from app.db import get_session
from app.models import User
from app.services import auth_service

bearer_scheme = HTTPBearer(auto_error=False)


def get_now() -> datetime:
    """The current instant. A dependency so tests can freeze it."""
    return datetime.now(UTC)


SessionDep = Annotated[Session, Depends(get_session)]
NowDep = Annotated[datetime, Depends(get_now)]


def current_user(
    session: SessionDep,
    now: NowDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise Unauthorized(ErrorCode.invalid_token, "Authentication required.")
    return auth_service.authenticate_token(session, credentials.credentials, now=now)


CurrentUser = Annotated[User, Depends(current_user)]
