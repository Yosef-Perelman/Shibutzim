from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, NowDep, SessionDep
from app.schemas.time_entry import TimeEntryCreate, TimeEntryOut, TimeEntryUpdate
from app.services import time_entry_service

router = APIRouter(prefix="/api/time-entries", tags=["time-entries"])


@router.post("/clock-in", status_code=201)
def clock_in(user: CurrentUser, session: SessionDep, now: NowDep) -> TimeEntryOut:
    return TimeEntryOut.model_validate(time_entry_service.clock_in(session, user, now=now))


@router.post("/clock-out")
def clock_out(user: CurrentUser, session: SessionDep, now: NowDep) -> TimeEntryOut:
    return TimeEntryOut.model_validate(time_entry_service.clock_out(session, user, now=now))


@router.get("")
def list_time_entries(
    user: CurrentUser,
    session: SessionDep,
    user_id: int | None = None,
    from_day: Annotated[date | None, Query(alias="from")] = None,
    to_day: Annotated[date | None, Query(alias="to")] = None,
) -> list[TimeEntryOut]:
    entries = time_entry_service.list_time_entries(
        session, user, user_id=user_id, from_day=from_day, to_day=to_day
    )
    return [TimeEntryOut.model_validate(entry) for entry in entries]


@router.post("", status_code=201)
def create_time_entry(
    body: TimeEntryCreate, user: CurrentUser, session: SessionDep
) -> TimeEntryOut:
    entry = time_entry_service.create_time_entry(session, user, **body.model_dump())
    return TimeEntryOut.model_validate(entry)


@router.patch("/{entry_id}")
def update_time_entry(
    entry_id: int, body: TimeEntryUpdate, user: CurrentUser, session: SessionDep
) -> TimeEntryOut:
    changes = body.model_dump(exclude_unset=True)
    entry = time_entry_service.update_time_entry(session, user, entry_id, changes=changes)
    return TimeEntryOut.model_validate(entry)


@router.delete("/{entry_id}", status_code=204)
def delete_time_entry(entry_id: int, user: CurrentUser, session: SessionDep) -> None:
    time_entry_service.delete_time_entry(session, user, entry_id)
