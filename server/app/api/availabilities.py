from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, NowDep, SessionDep
from app.schemas.availability import AvailabilityOut, AvailabilitySet
from app.services import availability_service

router = APIRouter(prefix="/api/availabilities", tags=["availabilities"])

WeekStart = Annotated[date, Query(description="The Sunday that starts the week")]


@router.get("")
def list_availabilities(
    user: CurrentUser, session: SessionDep, week_start: WeekStart, user_id: int | None = None
) -> list[AvailabilityOut]:
    rows = availability_service.list_availabilities(session, user, week_start, user_id=user_id)
    return [AvailabilityOut.model_validate(row) for row in rows]


@router.put("")
def set_availabilities(
    body: AvailabilitySet, user: CurrentUser, session: SessionDep, now: NowDep
) -> list[AvailabilityOut]:
    answers = {item.shift_id: item.status for item in body.items}
    rows = availability_service.set_availabilities(
        session, user, body.week_start, answers, user_id=body.user_id, now=now
    )
    return [AvailabilityOut.model_validate(row) for row in rows]
