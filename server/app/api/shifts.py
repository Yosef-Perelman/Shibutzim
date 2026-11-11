from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, SessionDep
from app.schemas.shift import ShiftGenerate, ShiftGenerateOut, ShiftOut
from app.services import shift_service

router = APIRouter(prefix="/api/shifts", tags=["shifts"])

WeekStart = Annotated[date, Query(description="The Sunday that starts the week")]


@router.post("/generate")
def generate_shifts(
    body: ShiftGenerate, user: CurrentUser, session: SessionDep
) -> ShiftGenerateOut:
    result = shift_service.generate_shifts(session, user, body.week_start)
    return ShiftGenerateOut(
        week_start=body.week_start,
        created=result.created,
        shifts=[ShiftOut.model_validate(shift) for shift in result.shifts],
    )


@router.get("")
def list_shifts(user: CurrentUser, session: SessionDep, week_start: WeekStart) -> list[ShiftOut]:
    shifts = shift_service.list_shifts(session, user, week_start)
    return [ShiftOut.model_validate(shift) for shift in shifts]
