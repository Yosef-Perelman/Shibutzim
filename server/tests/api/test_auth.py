"""POST /api/auth/login and GET /api/auth/me: status codes, error shape, authentication."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.security import create_access_token
from app.models import User
from tests.factories import DEFAULT_PASSWORD, NOW, auth_headers, make_user

LOGIN = "/api/auth/login"
ME = "/api/auth/me"


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- login ---


def test_login_returns_a_bearer_token_and_the_user(client: TestClient, employee: User) -> None:
    response = client.post(LOGIN, json={"email": employee.email, "password": DEFAULT_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"] == {
        "id": employee.id,
        "email": employee.email,
        "name": employee.name,
        "role": "employee",
        "hourly_rate": "50.00",
        "is_active": True,
    }


def test_login_response_never_contains_the_password_hash(
    client: TestClient, employee: User
) -> None:
    response = client.post(LOGIN, json={"email": employee.email, "password": DEFAULT_PASSWORD})

    assert "password" not in response.text
    assert employee.password_hash not in response.text


def test_the_token_from_login_authenticates_me(client: TestClient, manager: User) -> None:
    token = client.post(LOGIN, json={"email": manager.email, "password": DEFAULT_PASSWORD}).json()[
        "access_token"
    ]

    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["id"] == manager.id


def test_login_with_a_wrong_password_returns_401(client: TestClient, employee: User) -> None:
    response = client.post(LOGIN, json={"email": employee.email, "password": "nope"})

    assert response.status_code == 401
    assert error_code(response) == "invalid_credentials"


def test_login_with_an_unknown_email_returns_the_same_401(client: TestClient) -> None:
    response = client.post(LOGIN, json={"email": "ghost@example.com", "password": "nope"})

    assert response.status_code == 401
    assert error_code(response) == "invalid_credentials"


def test_login_of_an_inactive_user_returns_401(client: TestClient, session: Session) -> None:
    inactive = make_user(session, is_active=False)

    response = client.post(LOGIN, json={"email": inactive.email, "password": DEFAULT_PASSWORD})

    assert response.status_code == 401
    assert error_code(response) == "invalid_credentials"


def test_login_without_a_password_returns_422_validation_error(client: TestClient) -> None:
    response = client.post(LOGIN, json={"email": "a@example.com"})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_login_with_a_very_long_password_returns_422_not_500(client: TestClient) -> None:
    response = client.post(LOGIN, json={"email": "a@example.com", "password": "x" * 500})

    assert response.status_code == 422


# --- me ---


def test_me_returns_the_current_user(employee_client: TestClient, employee: User) -> None:
    response = employee_client.get(ME)

    assert response.status_code == 200
    assert response.json()["email"] == employee.email
    assert response.json()["role"] == "employee"


def test_me_without_a_token_returns_401(client: TestClient) -> None:
    response = client.get(ME)

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_with_an_expired_token_returns_401_token_expired(
    client: TestClient, employee: User
) -> None:
    headers = auth_headers(employee, now=NOW - timedelta(hours=9))

    response = client.get(ME, headers=headers)

    assert response.status_code == 401
    assert error_code(response) == "token_expired"


def test_me_with_a_garbage_token_returns_401(client: TestClient) -> None:
    response = client.get(ME, headers={"Authorization": "Bearer not.a.token"})

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


def test_me_with_a_non_bearer_scheme_returns_401(client: TestClient, employee: User) -> None:
    token = create_access_token(employee.id, Role.employee, now=NOW)

    response = client.get(ME, headers={"Authorization": f"Basic {token}"})

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


def test_me_with_the_token_of_a_deactivated_user_returns_401(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    headers = auth_headers(user)
    user.is_active = False
    session.flush()

    response = client.get(ME, headers=headers)

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"
