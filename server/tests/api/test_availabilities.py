"""Availability endpoints: shape, status codes, error shape and the 401 / 403 matrix."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import AvailabilityStatus
from app.models import User
from tests.factories import (
    NEXT_WEEK,
    THIS_WEEK,
    make_availability,
    make_schedule,
    make_shift,
)

BASE = "/api/availabilities"
WEEK = NEXT_WEEK.isoformat()


def error_code(response) -> str:
    return response.json()["error"]["code"]


def put_body(*items: tuple[int, str], **extra) -> dict:
    return {
        "week_start": WEEK,
        "items": [{"shift_id": shift_id, "status": status} for shift_id, status in items],
        **extra,
    }


# --- authentication ---


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [("GET", f"{BASE}?week_start={WEEK}", None), ("PUT", BASE, put_body((1, "available")))],
    ids=["list", "set"],
)
def test_endpoint_without_a_token_returns_401(client: TestClient, method, path, body) -> None:
    response = client.request(method, path, json=body)

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


# --- authorization ---


def test_reading_another_employees_answers_returns_403(
    employee_client: TestClient, other_employee: User
) -> None:
    response = employee_client.get(BASE, params={"week_start": WEEK, "user_id": other_employee.id})

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_answering_for_another_employee_returns_403(
    employee_client: TestClient, session: Session, other_employee: User
) -> None:
    shift = make_shift(session)

    response = employee_client.put(
        BASE, json=put_body((shift.id, "available"), user_id=other_employee.id)
    )

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


# --- reading ---


def test_an_employee_reads_their_own_answers(
    employee_client: TestClient, session: Session, employee: User, other_employee: User
) -> None:
    shift = make_shift(session)
    answer = make_availability(session, shift, employee, AvailabilityStatus.preferred)
    make_availability(session, shift, other_employee)

    response = employee_client.get(BASE, params={"week_start": WEEK})

    assert response.status_code == 200
    assert response.json() == [
        {"id": answer.id, "shift_id": shift.id, "user_id": employee.id, "status": "preferred"}
    ]


def test_a_manager_reads_the_whole_team(
    manager_client: TestClient, session: Session, employee: User, other_employee: User
) -> None:
    shift = make_shift(session)
    make_availability(session, shift, employee)
    make_availability(session, shift, other_employee)

    response = manager_client.get(BASE, params={"week_start": WEEK})

    assert {row["user_id"] for row in response.json()} == {employee.id, other_employee.id}


def test_a_manager_asking_for_an_unknown_user_returns_404(manager_client: TestClient) -> None:
    response = manager_client.get(BASE, params={"week_start": WEEK, "user_id": 999_999})

    assert response.status_code == 404
    assert error_code(response) == "user_not_found"


# --- answering ---


def test_an_employee_answers_and_gets_the_saved_rows_back(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    first, second = make_shift(session), make_shift(session)

    response = employee_client.put(
        BASE, json=put_body((first.id, "available"), (second.id, "unavailable"))
    )

    assert response.status_code == 200
    assert {(row["shift_id"], row["status"]) for row in response.json()} == {
        (first.id, "available"),
        (second.id, "unavailable"),
    }
    assert all(row["user_id"] == employee.id for row in response.json())


def test_a_manager_answers_for_an_employee(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    shift = make_shift(session)

    response = manager_client.put(BASE, json=put_body((shift.id, "preferred"), user_id=employee.id))

    assert response.status_code == 200
    assert response.json()[0]["user_id"] == employee.id


def test_answering_after_a_schedule_exists_returns_409(
    employee_client: TestClient, session: Session
) -> None:
    shift = make_shift(session)
    make_schedule(session)

    response = employee_client.put(BASE, json=put_body((shift.id, "available")))

    assert response.status_code == 409
    assert error_code(response) == "availability_locked"


def test_answering_for_a_past_week_returns_409(
    employee_client: TestClient, session: Session
) -> None:
    shift = make_shift(session, week_start=THIS_WEEK.replace(day=1))  # Sunday 2026-03-01

    response = employee_client.put(
        BASE,
        json={
            "week_start": "2026-03-01",
            "items": [{"shift_id": shift.id, "status": "available"}],
        },
    )

    assert response.status_code == 409
    assert error_code(response) == "availability_locked"


def test_answering_for_an_unknown_shift_returns_404(employee_client: TestClient) -> None:
    response = employee_client.put(BASE, json=put_body((999_999, "available")))

    assert response.status_code == 404
    assert error_code(response) == "shift_not_found"


def test_answering_for_a_shift_of_another_week_returns_422(
    employee_client: TestClient, session: Session
) -> None:
    other = make_shift(session, week_start=THIS_WEEK)

    response = employee_client.put(BASE, json=put_body((other.id, "available")))

    assert response.status_code == 422
    assert error_code(response) == "shift_not_in_week"


def test_answering_for_a_manager_returns_422(
    manager_client: TestClient, session: Session, manager: User
) -> None:
    shift = make_shift(session)

    response = manager_client.put(BASE, json=put_body((shift.id, "available"), user_id=manager.id))

    assert response.status_code == 422
    assert error_code(response) == "user_not_assignable"


@pytest.mark.parametrize(
    "body",
    [
        {"week_start": WEEK, "items": []},
        {"week_start": WEEK},
        {"items": [{"shift_id": 1, "status": "available"}]},
        {"week_start": WEEK, "items": [{"shift_id": 1, "status": "maybe"}]},
        {
            "week_start": WEEK,
            "items": [
                {"shift_id": 1, "status": "available"},
                {"shift_id": 1, "status": "preferred"},
            ],
        },
        {"week_start": "2026-03-16", "items": [{"shift_id": 1, "status": "available"}]},
    ],
    ids=["no_items", "no_items_key", "no_week", "bad_status", "duplicate_shift", "monday"],
)
def test_answering_with_a_bad_body_returns_422(employee_client: TestClient, body: dict) -> None:
    response = employee_client.put(BASE, json=body)

    assert response.status_code == 422
    assert error_code(response) in {"validation_error", "invalid_week_start"}


def test_reading_without_a_week_returns_422(employee_client: TestClient) -> None:
    response = employee_client.get(BASE)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
