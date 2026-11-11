"""User listing endpoint: shape, filters, error shape and the 401 / 403 matrix."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import make_user

BASE = "/api/users"


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- authentication and authorization ---


def test_list_without_a_token_returns_401(client: TestClient) -> None:
    response = client.get(BASE)

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


def test_list_by_an_employee_returns_403(employee_client: TestClient) -> None:
    response = employee_client.get(BASE)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


# --- listing ---


def test_list_by_a_manager_returns_users_ordered_by_name(
    manager_client: TestClient, employee: User, other_employee: User
) -> None:
    response = manager_client.get(BASE)

    assert response.status_code == 200
    assert [user["name"] for user in response.json()] == [
        "Dana Other",
        "Eli Employee",
        "Mia Manager",
    ]


def test_list_shows_the_fields_of_the_user_schema_and_never_the_password_hash(
    manager_client: TestClient, employee: User
) -> None:
    response = manager_client.get(BASE, params={"role": "employee"})

    assert response.json() == [
        {
            "id": employee.id,
            "email": employee.email,
            "name": "Eli Employee",
            "role": "employee",
            "hourly_rate": "50.00",
            "is_active": True,
        }
    ]


def test_list_filters_by_role(manager_client: TestClient, employee: User) -> None:
    response = manager_client.get(BASE, params={"role": "manager"})

    assert [user["name"] for user in response.json()] == ["Mia Manager"]


def test_list_filters_by_active_state(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    make_user(session, name="Aaron Gone", is_active=False)

    inactive = manager_client.get(BASE, params={"is_active": "false"})
    active_employees = manager_client.get(BASE, params={"role": "employee", "is_active": "true"})

    assert [user["name"] for user in inactive.json()] == ["Aaron Gone"]
    assert [user["name"] for user in active_employees.json()] == ["Eli Employee"]


# --- request validation ---


def test_list_with_an_unknown_role_returns_422(manager_client: TestClient) -> None:
    response = manager_client.get(BASE, params={"role": "owner"})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_list_with_a_malformed_active_flag_returns_422(manager_client: TestClient) -> None:
    response = manager_client.get(BASE, params={"is_active": "maybe"})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
