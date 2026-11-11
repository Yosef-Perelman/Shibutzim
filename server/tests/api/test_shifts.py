"""Shift endpoints: shape, status codes, error shape and the 401 / 403 matrix."""

from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import NEXT_WEEK, THIS_WEEK, make_shift, make_shift_template

BASE = "/api/shifts"
GENERATE = f"{BASE}/generate"
WEEK = NEXT_WEEK.isoformat()


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- authentication and authorization ---


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [("GET", f"{BASE}?week_start={WEEK}", None), ("POST", GENERATE, {"week_start": WEEK})],
    ids=["list", "generate"],
)
def test_endpoint_without_a_token_returns_401(client: TestClient, method, path, body) -> None:
    response = client.request(method, path, json=body)

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


def test_generate_by_an_employee_returns_403(employee_client: TestClient) -> None:
    response = employee_client.post(GENERATE, json={"week_start": WEEK})

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


# --- generate ---


def test_generate_returns_the_created_shifts(manager_client: TestClient, session: Session) -> None:
    template = make_shift_template(
        session, name="Morning", weekday=1, start_time=time(7, 0), end_time=time(15, 0)
    )

    response = manager_client.post(GENERATE, json={"week_start": WEEK})

    assert response.status_code == 200
    body = response.json()
    assert body["week_start"] == WEEK
    assert body["created"] == 1
    assert body["shifts"] == [
        {
            "id": body["shifts"][0]["id"],
            "template_id": template.id,
            "name": "Morning",
            "week_start": WEEK,
            "starts_at": "2026-03-16T05:00:00Z",
            "ends_at": "2026-03-16T13:00:00Z",
            "required_staff": 2,
        }
    ]


def test_generate_again_creates_nothing(manager_client: TestClient, session: Session) -> None:
    make_shift_template(session)
    manager_client.post(GENERATE, json={"week_start": WEEK})

    response = manager_client.post(GENERATE, json={"week_start": WEEK})

    assert response.status_code == 200
    assert response.json()["created"] == 0
    assert len(response.json()["shifts"]) == 1


def test_generate_for_a_day_that_is_not_a_sunday_returns_422(manager_client: TestClient) -> None:
    response = manager_client.post(GENERATE, json={"week_start": "2026-03-16"})

    assert response.status_code == 422
    assert error_code(response) == "invalid_week_start"


@pytest.mark.parametrize(
    "body", [{}, {"week_start": "not-a-date"}, {"week_start": None}], ids=["empty", "bad", "null"]
)
def test_generate_with_a_bad_body_returns_422(manager_client: TestClient, body: dict) -> None:
    response = manager_client.post(GENERATE, json=body)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


# --- list ---


def test_an_employee_can_list_a_weeks_shifts(employee_client: TestClient, session: Session) -> None:
    make_shift(session, make_shift_template(session, name="Morning"), week_start=NEXT_WEEK)
    make_shift(session, make_shift_template(session), week_start=THIS_WEEK)

    response = employee_client.get(BASE, params={"week_start": WEEK})

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Morning"]


def test_list_for_a_day_that_is_not_a_sunday_returns_422(employee_client: TestClient) -> None:
    response = employee_client.get(BASE, params={"week_start": "2026-03-16"})

    assert response.status_code == 422
    assert error_code(response) == "invalid_week_start"


def test_list_without_a_week_returns_422(employee_client: TestClient) -> None:
    response = employee_client.get(BASE)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
