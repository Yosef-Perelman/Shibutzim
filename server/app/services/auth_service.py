"""Login and token authentication (architecture §6.1)."""

from datetime import datetime
from functools import cache

from sqlalchemy.orm import Session

from app.core.errors import ErrorCode, Unauthorized
from app.core.security import (
    INVALID_TOKEN_MESSAGE,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.repositories import user_repository

INVALID_CREDENTIALS_MESSAGE = "Wrong email or password."


@cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def login(session: Session, email: str, password: str, *, now: datetime) -> tuple[str, User]:
    """Return an access token and the user. Every failure looks identical to the caller.

    Unknown email, wrong password and inactive account raise the same error, and an unknown email
    still pays for one bcrypt check, so neither message nor timing reveals which emails exist.
    """
    user = user_repository.get_by_email(session, normalize_email(email))
    password_ok = verify_password(password, user.password_hash if user else _dummy_hash())
    if user is None or not password_ok or not user.is_active:
        raise Unauthorized(ErrorCode.invalid_credentials, INVALID_CREDENTIALS_MESSAGE)
    return create_access_token(user.id, user.role, now=now), user


def authenticate_token(session: Session, token: str, *, now: datetime) -> User:
    """The user behind a valid token, loaded fresh from the database on every request.

    A deactivated or deleted user, or a token whose role differs from the database row, is rejected.
    """
    claims = decode_access_token(token, now=now)
    user = user_repository.get_by_id(session, claims.user_id)
    if user is None or not user.is_active or user.role is not claims.role:
        raise Unauthorized(ErrorCode.invalid_token, INVALID_TOKEN_MESSAGE)
    return user
