"""Login and token authentication (architecture §6.1)."""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import ErrorCode, Unauthorized
from app.core.security import create_access_token, decode_access_token
from app.models import User
from app.services import auth_service
from tests.factories import DEFAULT_PASSWORD, NOW, make_user


def test_login_returns_a_token_for_the_user(session: Session, employee: User) -> None:
    token, user = auth_service.login(session, employee.email, DEFAULT_PASSWORD, now=NOW)

    assert user.id == employee.id
    claims = decode_access_token(token, now=NOW)
    assert (claims.user_id, claims.role) == (employee.id, Role.employee)


def test_login_ignores_email_case_and_surrounding_spaces(session: Session, employee: User) -> None:
    _, user = auth_service.login(session, f"  {employee.email.upper()} ", DEFAULT_PASSWORD, now=NOW)

    assert user.id == employee.id


def test_login_with_a_wrong_password_is_invalid_credentials(
    session: Session, employee: User
) -> None:
    with pytest.raises(Unauthorized) as raised:
        auth_service.login(session, employee.email, "wrong-password", now=NOW)

    assert raised.value.code == ErrorCode.invalid_credentials


def test_login_with_an_unknown_email_looks_the_same_as_a_wrong_password(
    session: Session, employee: User
) -> None:
    with pytest.raises(Unauthorized) as wrong_password:
        auth_service.login(session, employee.email, "wrong-password", now=NOW)
    with pytest.raises(Unauthorized) as unknown_email:
        auth_service.login(session, "nobody@example.com", "wrong-password", now=NOW)

    assert unknown_email.value.code == wrong_password.value.code
    assert unknown_email.value.message == wrong_password.value.message


def test_login_of_an_inactive_user_is_invalid_credentials(session: Session) -> None:
    inactive = make_user(session, is_active=False)

    with pytest.raises(Unauthorized) as raised:
        auth_service.login(session, inactive.email, DEFAULT_PASSWORD, now=NOW)

    assert raised.value.code == ErrorCode.invalid_credentials


def test_authenticate_token_returns_the_user(session: Session, manager: User) -> None:
    token = create_access_token(manager.id, manager.role, now=NOW)

    user = auth_service.authenticate_token(session, token, now=NOW)

    assert user.id == manager.id


def test_authenticate_token_rejects_an_expired_token(session: Session, employee: User) -> None:
    token = create_access_token(employee.id, employee.role, now=NOW - timedelta(hours=9))

    with pytest.raises(Unauthorized) as raised:
        auth_service.authenticate_token(session, token, now=NOW)

    assert raised.value.code == ErrorCode.token_expired


def test_authenticate_token_rejects_a_user_who_became_inactive(session: Session) -> None:
    user = make_user(session)
    token = create_access_token(user.id, user.role, now=NOW)
    user.is_active = False
    session.flush()

    with pytest.raises(Unauthorized) as raised:
        auth_service.authenticate_token(session, token, now=NOW)

    assert raised.value.code == ErrorCode.invalid_token


def test_authenticate_token_rejects_a_user_that_no_longer_exists(session: Session) -> None:
    token = create_access_token(999_999, Role.employee, now=NOW)

    with pytest.raises(Unauthorized) as raised:
        auth_service.authenticate_token(session, token, now=NOW)

    assert raised.value.code == ErrorCode.invalid_token


def test_authenticate_token_rejects_a_role_that_differs_from_the_database(
    session: Session, employee: User
) -> None:
    token = create_access_token(
        employee.id, Role.manager, now=NOW
    )  # an employee with a manager token

    with pytest.raises(Unauthorized) as raised:
        auth_service.authenticate_token(session, token, now=NOW)

    assert raised.value.code == ErrorCode.invalid_token
