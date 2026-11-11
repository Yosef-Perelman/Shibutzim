"""Schedule endpoints: generate, read, edit assignments and publish (401 / 403 matrix included)."""

from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import AvailabilityStatus, ScheduleStatus
from app.models import User
from tests.factories import (
    NEXT_WEEK,
    make_assignment,
    make_availability,
    make_schedule,
    make_shift,
    make_shift_template,
)

WEEK = NEXT_WEEK.isoformat()
BASE = f"/api/schedules/{WEEK}"


def error_code(response) -> str:
    return response.json()["error"]["code"]


def monday_shift(session: Session, *, staff: int = 1, hour: int = 7):
    template = make_shift_template(
        session,
        name="Morning",
        weekday=1,
        start_time=time(hour, 0),
        end_time=time(hour + 8, 0),
        required_staff=staff,
    )
    return make_shift(session, template)


# --- authentication: every endpoint rejects a call without a token ---


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", BASE),
        ("POST", f"{BASE}/generate"),
    ],
    ids=["get", "generate"],
)
def test_endpoint_without_a_token_returns_401(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={} if method in {"POST", "PATCH"} else None)

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


# --- authorization: managers only, except reading a published schedule ---


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", f"{BASE}/generate"),
    ],
    ids=["generate"],
)
def test_manager_only_endpoints_return_403_for_an_employee(
    employee_client: TestClient, method: str, path: str
) -> None:
    response = employee_client.request(
        method, path, json={} if method in {"POST", "PATCH"} else None
    )

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_an_employee_gets_404_for_a_draft(employee_client: TestClient, session: Session) -> None:
    make_schedule(session)

    response = employee_client.get(BASE)

    assert response.status_code == 404
    assert error_code(response) == "schedule_not_found"


# --- generate ---


def test_generate_returns_the_draft_the_unfilled_slots_and_the_score(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    shift = monday_shift(session, staff=2)
    make_availability(session, shift, employee, AvailabilityStatus.preferred)

    response = manager_client.post(f"{BASE}/generate")

    assert response.status_code == 200
    body = response.json()
    assert body["schedule"]["status"] == "draft"
    assert body["schedule"]["week_start"] == WEEK
    assert [
        (a["shift_id"], a["user_id"], a["user_name"]) for a in body["schedule"]["assignments"]
    ] == [(shift.id, employee.id, "Eli Employee")]
    assert body["schedule"]["shifts"] == [
        {
            "shift_id": shift.id,
            "name": "Morning",
            "starts_at": "2026-03-16T05:00:00Z",
            "ends_at": "2026-03-16T13:00:00Z",
            "required_staff": 2,
            "assigned_count": 1,
            "unfilled_count": 1,
        }
    ]
    assert body["unfilled"] == [
        {
            "shift_id": shift.id,
            "required": 2,
            "assigned": 1,
            "missing": 1,
            "reasons": [],
            "sentence": "Monday 07:00 needs 2, only 1 available",
        }
    ]
    assert body["score"] == {"filled": 1, "preferred": 1, "spread_minutes": 0, "value": 120}
    assert body["complete"] is True


def test_generate_names_who_is_excluded_and_why(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    morning, evening = monday_shift(session, hour=7), monday_shift(session, hour=15)
    make_availability(session, morning, employee)
    make_availability(session, evening, employee)

    response = manager_client.post(f"{BASE}/generate")

    reason = response.json()["unfilled"][0]["reasons"][0]
    assert reason == {
        "user_id": employee.id,
        "user_name": "Eli Employee",
        "constraint": "min_rest",
        "shift_id": morning.id,
    }


def test_generate_without_shifts_returns_422(manager_client: TestClient) -> None:
    response = manager_client.post(f"{BASE}/generate")

    assert response.status_code == 422
    assert error_code(response) == "no_shifts_for_week"


def test_generate_for_a_published_week_returns_409(
    manager_client: TestClient, session: Session
) -> None:
    monday_shift(session)
    make_schedule(session, status=ScheduleStatus.published)

    response = manager_client.post(f"{BASE}/generate")

    assert response.status_code == 409
    assert error_code(response) == "schedule_published"


def test_generate_for_a_day_that_is_not_a_sunday_returns_422(manager_client: TestClient) -> None:
    response = manager_client.post("/api/schedules/2026-03-16/generate")

    assert response.status_code == 422
    assert error_code(response) == "invalid_week_start"


def test_a_malformed_week_in_the_path_returns_422(manager_client: TestClient) -> None:
    response = manager_client.get("/api/schedules/next-week")

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


# --- read ---


def test_a_manager_reads_a_draft(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    shift = monday_shift(session)
    schedule = make_schedule(session)
    make_assignment(session, schedule, shift, employee)

    response = manager_client.get(BASE)

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["status"], body["published_at"]) == (schedule.id, "draft", None)
    assert body["assignments"][0]["starts_at"] == "2026-03-16T05:00:00Z"


def test_an_employee_reads_a_published_schedule(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    shift = monday_shift(session)
    schedule = make_schedule(session, status=ScheduleStatus.published)
    make_assignment(session, schedule, shift, employee)

    response = employee_client.get(BASE)

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["published_at"] == "2026-03-09T12:00:00Z"


def test_reading_a_week_without_a_schedule_returns_404(manager_client: TestClient) -> None:
    response = manager_client.get(BASE)

    assert response.status_code == 404
    assert error_code(response) == "schedule_not_found"
