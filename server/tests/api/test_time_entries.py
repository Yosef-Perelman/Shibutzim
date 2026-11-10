"""Time-entry endpoints: routing, status codes, error shape and the 401 / 403 matrix."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import NOW, make_time_entry

BASE = "/api/time-entries"
CREATE_BODY = {"clock_in": "2026-03-09T05:00:00Z", "clock_out": "2026-03-09T09:00:00Z"}


def error_code(response) -> str:
    return response.json()["error"]["code"]


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


# --- authentication: every endpoint rejects a call without a token ---


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", f"{BASE}/clock-in"),
        ("POST", f"{BASE}/clock-out"),
        ("GET", BASE),
        ("POST", BASE),
        ("PATCH", f"{BASE}/1"),
        ("DELETE", f"{BASE}/1"),
    ],
    ids=["clock_in", "clock_out", "list", "create", "update", "delete"],
)
def test_endpoint_without_a_token_returns_401(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={} if method in {"POST", "PATCH"} else None)

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


# --- authorization: manager-only endpoints reject employees ---


def test_create_by_an_employee_returns_403(employee_client: TestClient, employee: User) -> None:
    body = {"user_id": employee.id, **CREATE_BODY}

    response = employee_client.post(BASE, json=body)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_update_by_an_employee_returns_403(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    entry = make_time_entry(session, employee)

    response = employee_client.patch(f"{BASE}/{entry.id}", json={"note": "mine"})

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_delete_by_an_employee_returns_403(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    entry = make_time_entry(session, employee)

    response = employee_client.delete(f"{BASE}/{entry.id}")

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_list_of_another_employee_returns_403(
    employee_client: TestClient, other_employee: User
) -> None:
    response = employee_client.get(BASE, params={"user_id": other_employee.id})

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


# --- clock in / clock out ---


def test_clock_in_returns_201_with_an_open_entry(
    employee_client: TestClient, employee: User
) -> None:
    response = employee_client.post(f"{BASE}/clock-in")

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == employee.id
    assert parse(body["clock_in"]) == NOW
    assert body["clock_out"] is None
    assert body["source"] == "clock"
    assert body["created_by"] == employee.id


def test_second_clock_in_returns_409_already_clocked_in(employee_client: TestClient) -> None:
    employee_client.post(f"{BASE}/clock-in")

    response = employee_client.post(f"{BASE}/clock-in")

    assert response.status_code == 409
    assert error_code(response) == "already_clocked_in"


def test_clock_out_returns_the_closed_entry(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=NOW - timedelta(hours=8), duration=None)

    response = employee_client.post(f"{BASE}/clock-out")

    assert response.status_code == 200
    assert parse(response.json()["clock_out"]) == NOW


def test_clock_out_without_an_open_entry_returns_409_not_clocked_in(
    employee_client: TestClient,
) -> None:
    response = employee_client.post(f"{BASE}/clock-out")

    assert response.status_code == 409
    assert error_code(response) == "not_clocked_in"


def test_clock_out_after_more_than_24_hours_returns_422_entry_too_long(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=NOW - timedelta(hours=30), duration=None)

    response = employee_client.post(f"{BASE}/clock-out")

    assert response.status_code == 422
    assert error_code(response) == "entry_too_long"


def test_clock_out_at_the_instant_of_clock_in_returns_422(employee_client: TestClient) -> None:
    employee_client.post(f"{BASE}/clock-in")

    response = employee_client.post(f"{BASE}/clock-out")  # the frozen clock has not moved

    assert response.status_code == 422
    assert error_code(response) == "clock_out_before_clock_in"
    assert employee_client.get(BASE).json()[0]["clock_out"] is None


# --- list ---


def test_list_returns_own_entries_in_clock_in_order(
    employee_client: TestClient, session: Session, employee: User, other_employee: User
) -> None:
    later = make_time_entry(session, employee, clock_in=NOW - timedelta(days=1))
    earlier = make_time_entry(session, employee, clock_in=NOW - timedelta(days=3))
    make_time_entry(session, other_employee)

    response = employee_client.get(BASE)

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [earlier.id, later.id]


def test_list_as_manager_for_an_employee(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    entry = make_time_entry(session, employee)

    response = manager_client.get(BASE, params={"user_id": employee.id})

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [entry.id]


def test_list_filters_by_work_day_range(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=datetime(2026, 3, 9, 5, 0, tzinfo=UTC))
    inside = make_time_entry(session, employee, clock_in=datetime(2026, 3, 10, 5, 0, tzinfo=UTC))

    response = employee_client.get(BASE, params={"from": "2026-03-10", "to": "2026-03-10"})

    assert [e["id"] for e in response.json()] == [inside.id]


def test_list_with_from_after_to_returns_422(employee_client: TestClient) -> None:
    response = employee_client.get(BASE, params={"from": "2026-03-10", "to": "2026-03-09"})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_list_with_a_malformed_date_returns_422(employee_client: TestClient) -> None:
    response = employee_client.get(BASE, params={"from": "yesterday"})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_list_for_an_unknown_user_as_manager_returns_404(manager_client: TestClient) -> None:
    response = manager_client.get(BASE, params={"user_id": 999_999})

    assert response.status_code == 404
    assert error_code(response) == "user_not_found"


# --- create (manager) ---


def test_create_returns_201_with_a_manual_entry(
    manager_client: TestClient, manager: User, employee: User
) -> None:
    response = manager_client.post(
        BASE, json={"user_id": employee.id, "note": "Forgot", **CREATE_BODY}
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["user_id"], body["source"], body["created_by"]) == (
        employee.id,
        "manual",
        manager.id,
    )
    assert body["note"] == "Forgot"


def test_create_with_clock_out_before_clock_in_returns_422(
    manager_client: TestClient, employee: User
) -> None:
    body = {
        "user_id": employee.id,
        "clock_in": "2026-03-09T09:00:00Z",
        "clock_out": "2026-03-09T05:00:00Z",
    }

    response = manager_client.post(BASE, json=body)

    assert response.status_code == 422
    assert error_code(response) == "clock_out_before_clock_in"


def test_create_longer_than_24_hours_returns_422_entry_too_long(
    manager_client: TestClient, employee: User
) -> None:
    body = {
        "user_id": employee.id,
        "clock_in": "2026-03-09T05:00:00Z",
        "clock_out": "2026-03-10T06:00:00Z",
    }

    response = manager_client.post(BASE, json=body)

    assert response.status_code == 422
    assert error_code(response) == "entry_too_long"


def test_create_overlapping_an_entry_returns_409(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=datetime(2026, 3, 9, 4, 0, tzinfo=UTC))

    response = manager_client.post(BASE, json={"user_id": employee.id, **CREATE_BODY})

    assert response.status_code == 409
    assert error_code(response) == "time_entry_overlap"


def test_create_with_a_naive_datetime_returns_422_validation_error(
    manager_client: TestClient, employee: User
) -> None:
    body = {
        "user_id": employee.id,
        "clock_in": "2026-03-09T05:00:00",
        "clock_out": CREATE_BODY["clock_out"],
    }

    response = manager_client.post(BASE, json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_create_for_an_unknown_user_returns_404(manager_client: TestClient) -> None:
    response = manager_client.post(BASE, json={"user_id": 999_999, **CREATE_BODY})

    assert response.status_code == 404
    assert error_code(response) == "user_not_found"


# --- update (manager) ---


def test_update_returns_the_corrected_entry(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    entry = make_time_entry(session, employee, clock_in=datetime(2026, 3, 9, 5, 0, tzinfo=UTC))

    response = manager_client.patch(
        f"{BASE}/{entry.id}", json={"clock_out": "2026-03-09T14:00:00Z", "note": "Stayed late"}
    )

    assert response.status_code == 200
    assert parse(response.json()["clock_out"]) == datetime(2026, 3, 9, 14, 0, tzinfo=UTC)
    assert response.json()["note"] == "Stayed late"


def test_update_with_an_empty_body_returns_422(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    entry = make_time_entry(session, employee)

    response = manager_client.patch(f"{BASE}/{entry.id}", json={})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_update_cannot_clear_clock_in(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    entry = make_time_entry(session, employee)

    response = manager_client.patch(f"{BASE}/{entry.id}", json={"clock_in": None})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_update_of_a_missing_entry_returns_404(manager_client: TestClient) -> None:
    response = manager_client.patch(f"{BASE}/999999", json={"note": "x"})

    assert response.status_code == 404
    assert error_code(response) == "time_entry_not_found"


# --- delete (manager) ---


def test_delete_returns_204_and_removes_the_entry(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    entry = make_time_entry(session, employee)

    response = manager_client.delete(f"{BASE}/{entry.id}")

    assert response.status_code == 204
    assert response.content == b""
    assert manager_client.get(BASE, params={"user_id": employee.id}).json() == []


def test_delete_of_a_missing_entry_returns_404(manager_client: TestClient) -> None:
    response = manager_client.delete(f"{BASE}/999999")

    assert response.status_code == 404
    assert error_code(response) == "time_entry_not_found"
