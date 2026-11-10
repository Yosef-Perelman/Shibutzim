"""Password hashing and JWTs (architecture §8). Time is passed in; nothing reads the clock."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import get_settings
from app.core.enums import Role
from app.core.errors import ErrorCode, Unauthorized
from app.core.security import (
    TokenClaims,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

NOW = datetime(2026, 3, 9, 12, 0, tzinfo=UTC)
ROUNDS = 4  # bcrypt's minimum, to keep the tests fast


# --- passwords ---


def test_hash_password_verifies_the_same_password() -> None:
    hashed = hash_password("s3cret-pass", rounds=ROUNDS)

    assert verify_password("s3cret-pass", hashed) is True


def test_verify_password_rejects_a_different_password() -> None:
    hashed = hash_password("s3cret-pass", rounds=ROUNDS)

    assert verify_password("S3cret-pass", hashed) is False


def test_hash_password_is_salted() -> None:
    assert hash_password("same", rounds=ROUNDS) != hash_password("same", rounds=ROUNDS)


def test_hash_password_never_contains_the_plain_password() -> None:
    assert "s3cret-pass" not in hash_password("s3cret-pass", rounds=ROUNDS)


def test_verify_password_returns_false_for_a_malformed_hash() -> None:
    assert verify_password("anything", "not-a-bcrypt-hash") is False


def test_passwords_over_72_bytes_are_rejected_when_hashing_and_never_match() -> None:
    too_long = "x" * 73

    with pytest.raises(ValueError, match="72"):
        hash_password(too_long, rounds=ROUNDS)
    assert verify_password(too_long, hash_password("x" * 72, rounds=ROUNDS)) is False


# --- tokens ---


def test_token_round_trips_user_id_and_role() -> None:
    token = create_access_token(42, Role.manager, now=NOW)

    claims = decode_access_token(token, now=NOW)

    assert claims == TokenClaims(user_id=42, role=Role.manager, expires_at=NOW + timedelta(hours=8))


def test_token_lifetime_comes_from_settings() -> None:
    token = create_access_token(1, Role.employee, now=NOW)

    payload = jwt.decode(token, options={"verify_signature": False})

    assert payload["exp"] - payload["iat"] == get_settings().jwt_expires_hours * 3600


def test_token_is_valid_just_before_it_expires() -> None:
    token = create_access_token(1, Role.employee, now=NOW)

    claims = decode_access_token(token, now=NOW + timedelta(hours=8) - timedelta(seconds=1))

    assert claims.user_id == 1


def test_token_is_expired_exactly_at_its_expiry_time() -> None:
    token = create_access_token(1, Role.employee, now=NOW)

    with pytest.raises(Unauthorized) as raised:
        decode_access_token(token, now=NOW + timedelta(hours=8))

    assert raised.value.code == ErrorCode.token_expired


def test_tampered_token_is_invalid() -> None:
    token = create_access_token(1, Role.employee, now=NOW)
    head, payload, signature = token.split(".")
    tampered = ".".join(
        [head, payload, signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")]
    )

    with pytest.raises(Unauthorized) as raised:
        decode_access_token(tampered, now=NOW)

    assert raised.value.code == ErrorCode.invalid_token


def test_token_signed_with_another_secret_is_invalid() -> None:
    forged = jwt.encode(
        {
            "sub": "1",
            "role": "manager",
            "iat": int(NOW.timestamp()),
            "exp": int(NOW.timestamp()) + 60,
        },
        "some-other-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
    )

    with pytest.raises(Unauthorized) as raised:
        decode_access_token(forged, now=NOW)

    assert raised.value.code == ErrorCode.invalid_token


def test_unsigned_token_is_invalid() -> None:
    unsigned = jwt.encode(
        {"sub": "1", "role": "manager", "exp": 4_000_000_000}, None, algorithm="none"
    )

    with pytest.raises(Unauthorized) as raised:
        decode_access_token(unsigned, now=NOW)

    assert raised.value.code == ErrorCode.invalid_token


@pytest.mark.parametrize(
    "garbage", ["", "abc", "a.b.c", "Bearer x"], ids=["empty", "word", "dots", "scheme"]
)
def test_garbage_token_is_invalid(garbage: str) -> None:
    with pytest.raises(Unauthorized) as raised:
        decode_access_token(garbage, now=NOW)

    assert raised.value.code == ErrorCode.invalid_token


def test_token_with_an_unknown_role_is_invalid() -> None:
    forged = jwt.encode(
        {
            "sub": "1",
            "role": "admin",
            "iat": int(NOW.timestamp()),
            "exp": int(NOW.timestamp()) + 60,
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )

    with pytest.raises(Unauthorized) as raised:
        decode_access_token(forged, now=NOW)

    assert raised.value.code == ErrorCode.invalid_token


def test_token_without_a_numeric_subject_is_invalid() -> None:
    forged = jwt.encode(
        {
            "sub": "abc",
            "role": "employee",
            "iat": int(NOW.timestamp()),
            "exp": int(NOW.timestamp()) + 60,
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )

    with pytest.raises(Unauthorized) as raised:
        decode_access_token(forged, now=NOW)

    assert raised.value.code == ErrorCode.invalid_token
