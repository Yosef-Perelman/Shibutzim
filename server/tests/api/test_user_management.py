"""Create and deactivate users: routing, status codes, error shape and the 401 / 403 matrix."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.conftest import api_client
from tests.factories import make_user

BASE = "/api/users"
CREATE_BODY = {
    "email": "noa.new@example.com",
    "name": "Noa New",
    "role": "employee",
    "hourly_rate": "42.50",
    "password": "first-password-1",
}


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- authentication and authorization ---


@pytest.mark.parametrize(
    ("method", "path"),
    [("POST", BASE), ("PATCH", f"{BASE}/1")],
    ids=["create", "set_active"],
)
def test_endpoint_without_a_token_returns_401(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={})

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


def test_create_by_an_employee_returns_403(employee_client: TestClient) -> None:
    response = employee_client.post(BASE, json=CREATE_BODY)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_set_active_by_an_employee_returns_403(
    employee_client: TestClient, other_employee: User
) -> None:
    response = employee_client.patch(f"{BASE}/{other_employee.id}", json={"is_active": False})

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_set_active_by_an_employee_for_a_missing_id_returns_403_not_404(
    employee_client: TestClient,
) -> None:
    response = employee_client.patch(f"{BASE}/999999", json={"is_active": False})

    assert response.status_code == 403


# --- create ---


def test_create_returns_201_and_the_new_user_without_a_password_hash(
    manager_client: TestClient,
) -> None:
    response = manager_client.post(BASE, json=CREATE_BODY)

    assert response.status_code == 201
    body = response.json()
    assert body.pop("id") > 0
    assert body == {
        "email": "noa.new@example.com",
        "name": "Noa New",
        "role": "employee",
        "hourly_rate": "42.50",
        "is_active": True,
    }


def test_create_defaults_the_role_to_employee(manager_client: TestClient) -> None:
    body = {key: value for key, value in CREATE_BODY.items() if key != "role"}

    response = manager_client.post(BASE, json=body)

    assert response.status_code == 201
    assert response.json()["role"] == "employee"


def test_the_created_person_can_log_in(manager_client: TestClient, client: TestClient) -> None:
    manager_client.post(BASE, json=CREATE_BODY)

    login = client.post(
        "/api/auth/login",
        json={"email": "noa.new@example.com", "password": "first-password-1"},
    )

    assert login.status_code == 200
    assert login.json()["user"]["name"] == "Noa New"


def test_create_appears_in_the_list(manager_client: TestClient) -> None:
    manager_client.post(BASE, json=CREATE_BODY)

    names = [user["name"] for user in manager_client.get(BASE).json()]

    assert "Noa New" in names


def test_create_with_an_existing_email_returns_409(
    manager_client: TestClient, employee: User
) -> None:
    response = manager_client.post(BASE, json={**CREATE_BODY, "email": employee.email})

    assert response.status_code == 409
    assert error_code(response) == "email_already_used"


# --- create: request validation ---


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "not-an-email"),
        ("email", ""),
        ("name", ""),
        ("name", "x" * 121),
        ("role", "owner"),
        ("hourly_rate", "0"),
        ("hourly_rate", "-5"),
        ("hourly_rate", "abc"),
        ("hourly_rate", "12.345"),
        ("password", "short"),
        ("password", "x" * 73),
    ],
    ids=[
        "bad_email",
        "empty_email",
        "empty_name",
        "long_name",
        "unknown_role",
        "zero_rate",
        "negative_rate",
        "text_rate",
        "three_decimals",
        "short_password",
        "long_password",
    ],
)
def test_create_with_invalid_input_returns_422(
    manager_client: TestClient, field: str, value: str
) -> None:
    response = manager_client.post(BASE, json={**CREATE_BODY, field: value})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


@pytest.mark.parametrize("field", ["email", "name", "hourly_rate", "password"])
def test_create_without_a_required_field_returns_422(
    manager_client: TestClient, field: str
) -> None:
    body = {key: value for key, value in CREATE_BODY.items() if key != field}

    response = manager_client.post(BASE, json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


# --- set active ---


def test_set_active_false_deactivates_and_returns_the_user(
    manager_client: TestClient, employee: User
) -> None:
    response = manager_client.patch(f"{BASE}/{employee.id}", json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["id"] == employee.id
    assert response.json()["is_active"] is False


def test_a_deactivated_person_is_rejected_on_their_next_request(
    manager_client: TestClient, employee: User
) -> None:
    manager_client.patch(f"{BASE}/{employee.id}", json={"is_active": False})

    response = api_client(employee).get("/api/auth/me")

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


def test_set_active_true_reactivates(manager_client: TestClient, session: Session) -> None:
    gone = make_user(session, is_active=False)

    response = manager_client.patch(f"{BASE}/{gone.id}", json={"is_active": True})

    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_set_active_for_a_missing_id_returns_404(manager_client: TestClient) -> None:
    response = manager_client.patch(f"{BASE}/999999", json={"is_active": False})

    assert response.status_code == 404
    assert error_code(response) == "user_not_found"


def test_a_manager_deactivating_themself_returns_422(
    manager_client: TestClient, manager: User
) -> None:
    response = manager_client.patch(f"{BASE}/{manager.id}", json={"is_active": False})

    assert response.status_code == 422
    assert error_code(response) == "cannot_deactivate_self"


@pytest.mark.parametrize(
    "body",
    [{}, {"is_active": "maybe"}, {"is_active": None}, {"is_active": False, "role": "manager"}],
    ids=["empty", "not_a_bool", "null", "extra_field"],
)
def test_set_active_with_invalid_input_returns_422(
    manager_client: TestClient, employee: User, body: dict
) -> None:
    response = manager_client.patch(f"{BASE}/{employee.id}", json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
