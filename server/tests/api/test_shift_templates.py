"""Shift-template endpoints: shape, status codes, error shape and the 401 / 403 matrix."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import make_shift_template

BASE = "/api/shift-templates"
CREATE_BODY = {
    "name": "Morning",
    "weekday": 0,
    "start_time": "07:00:00",
    "end_time": "15:00:00",
    "required_staff": 2,
}


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- authentication ---


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", BASE), ("POST", BASE), ("PATCH", f"{BASE}/1")],
    ids=["list", "create", "update"],
)
def test_endpoint_without_a_token_returns_401(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={} if method != "GET" else None)

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


# --- authorization: managers only ---


def test_list_by_an_employee_returns_403(employee_client: TestClient) -> None:
    response = employee_client.get(BASE)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_create_by_an_employee_returns_403(employee_client: TestClient) -> None:
    response = employee_client.post(BASE, json=CREATE_BODY)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_update_by_an_employee_returns_403_even_for_a_missing_id(
    employee_client: TestClient,
) -> None:
    response = employee_client.patch(f"{BASE}/999999", json={"name": "x"})

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


# --- happy paths ---


def test_create_returns_201_and_the_template(manager_client: TestClient) -> None:
    response = manager_client.post(BASE, json=CREATE_BODY)

    assert response.status_code == 201
    assert response.json() == {"id": response.json()["id"], **CREATE_BODY, "is_active": True}


def test_create_accepts_times_without_seconds(manager_client: TestClient) -> None:
    response = manager_client.post(BASE, json={**CREATE_BODY, "start_time": "07:00"})

    assert response.status_code == 201
    assert response.json()["start_time"] == "07:00:00"


def test_list_returns_templates_in_weekday_and_time_order(
    manager_client: TestClient, session: Session
) -> None:
    make_shift_template(session, name="Tue", weekday=2)
    make_shift_template(session, name="Mon", weekday=1)

    response = manager_client.get(BASE)

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Mon", "Tue"]


def test_list_active_only_hides_deactivated_templates(
    manager_client: TestClient, session: Session
) -> None:
    make_shift_template(session, name="Kept")
    make_shift_template(session, name="Gone", is_active=False)

    response = manager_client.get(BASE, params={"active_only": "true"})

    assert [item["name"] for item in response.json()] == ["Kept"]


def test_update_changes_the_template_and_returns_it(
    manager_client: TestClient, session: Session
) -> None:
    template = make_shift_template(session, name="Old")

    response = manager_client.patch(
        f"{BASE}/{template.id}", json={"name": "New", "is_active": False}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New"
    assert response.json()["is_active"] is False


# --- errors ---


def test_update_of_a_missing_template_returns_404(manager_client: TestClient) -> None:
    response = manager_client.patch(f"{BASE}/999999", json={"name": "x"})

    assert response.status_code == 404
    assert error_code(response) == "shift_template_not_found"


@pytest.mark.parametrize(
    "change",
    [
        {"weekday": 7},
        {"weekday": -1},
        {"required_staff": 0},
        {"name": ""},
        {"name": "   "},
        {"start_time": "25:00"},
        {"start_time": "07:00:00+02:00"},
        {"required_staff": 101},
    ],
    ids=[
        "weekday_seven",
        "weekday_negative",
        "zero_staff",
        "empty_name",
        "blank_name",
        "invalid_time",
        "time_with_offset",
        "absurd_staff",
    ],
)
def test_create_with_invalid_input_returns_422(manager_client: TestClient, change: dict) -> None:
    response = manager_client.post(BASE, json={**CREATE_BODY, **change})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_create_with_a_missing_field_returns_422(manager_client: TestClient) -> None:
    body = {key: value for key, value in CREATE_BODY.items() if key != "name"}

    response = manager_client.post(BASE, json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


@pytest.mark.parametrize(
    "body",
    [{}, {"name": None}, {"required_staff": 0}, {"unknown": 1}],
    ids=["empty_body", "null_name", "zero_staff", "unknown_field"],
)
def test_update_with_invalid_input_returns_422(
    manager_client: TestClient, session: Session, body: dict
) -> None:
    template = make_shift_template(session)

    response = manager_client.patch(f"{BASE}/{template.id}", json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
