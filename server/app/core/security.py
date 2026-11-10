"""Password hashing (bcrypt) and access tokens (JWT, HS256) – architecture §8.

Time is always passed in (`now`), never read here, so expiry is testable. The token carries `sub`
(user id) and `role`; the service cross-checks the role against the database row.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings
from app.core.enums import Role
from app.core.errors import ErrorCode, Unauthorized
from app.core.time import ensure_aware

ALGORITHM = "HS256"
DEFAULT_BCRYPT_ROUNDS = 12
BCRYPT_MAX_BYTES = (
    72  # bcrypt ignores (v4) or rejects (v5) anything longer, so we refuse it explicitly
)
INVALID_TOKEN_MESSAGE = "Invalid authentication token."


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    role: Role
    expires_at: datetime


def hash_password(password: str, *, rounds: int = DEFAULT_BCRYPT_ROUNDS) -> str:
    encoded = password.encode()
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise ValueError(f"password must be at most {BCRYPT_MAX_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """True only for a matching password; a malformed hash or over-long password never matches."""
    encoded = password.encode()
    if len(encoded) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode())
    except ValueError:
        return False


def create_access_token(user_id: int, role: Role, *, now: datetime) -> str:
    issued_at = int(ensure_aware(now).timestamp())
    lifetime = timedelta(hours=get_settings().jwt_expires_hours)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "iat": issued_at,
        "exp": issued_at + int(lifetime.total_seconds()),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str, *, now: datetime) -> TokenClaims:
    """Verify signature and structure, then expiry against `now`. Raises `Unauthorized`."""
    try:
        # Expiry is checked below against the injected `now`, not the system clock.
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "role", "exp"], "verify_exp": False, "verify_iat": False},
        )
        user_id = int(payload["sub"])
        role = Role(payload["role"])
        expires_at = datetime.fromtimestamp(float(payload["exp"]), tz=UTC)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise Unauthorized(ErrorCode.invalid_token, INVALID_TOKEN_MESSAGE) from None

    if expires_at <= ensure_aware(now):
        raise Unauthorized(
            ErrorCode.token_expired, "Your session has expired. Please log in again."
        )
    return TokenClaims(user_id=user_id, role=role, expires_at=expires_at)
