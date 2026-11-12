from datetime import date

from fastapi import APIRouter

from app.deps import CurrentUser, NowDep, SessionDep
from app.schemas.schedule import (
    AssignmentCreate,
    AssignmentEditOut,
    AssignmentOut,
    AssignmentUpdate,
    ReasonOut,
    ScheduleGenerateIn,
    ScheduleGenerateOut,
    ScheduleOut,
    ScoreOut,
    ShiftCoverageOut,
    UnfilledSlotOut,
    WarningOut,
)
from app.services import assignment_service, schedule_service
from app.services.assignment_service import AssignmentEdit
from app.services.schedule_service import DayOff, GeneratedSchedule, ScheduleView

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("/{week_start}")
def get_schedule(week_start: date, user: CurrentUser, session: SessionDep) -> ScheduleOut:
    return schedule_out(schedule_service.get_schedule(session, user, week_start))


@router.post("/{week_start}/generate")
def generate_schedule(
    week_start: date,
    user: CurrentUser,
    session: SessionDep,
    body: ScheduleGenerateIn | None = None,
) -> ScheduleGenerateOut:
    days_off = [DayOff(item.user_id, item.day) for item in body.unavailable] if body else []
    return generate_out(
        schedule_service.generate_schedule(session, user, week_start, unavailable=days_off)
    )


@router.post("/{week_start}/publish")
def publish_schedule(
    week_start: date, user: CurrentUser, session: SessionDep, now: NowDep
) -> ScheduleOut:
    return schedule_out(schedule_service.publish_schedule(session, user, week_start, now=now))


@router.post("/{week_start}/assignments", status_code=201)
def add_assignment(
    week_start: date, body: AssignmentCreate, user: CurrentUser, session: SessionDep
) -> AssignmentEditOut:
    edit = assignment_service.add_assignment(
        session, user, week_start, shift_id=body.shift_id, user_id=body.user_id
    )
    return edit_out(edit)


@router.patch("/{week_start}/assignments/{assignment_id}")
def replace_assignment(
    week_start: date,
    assignment_id: int,
    body: AssignmentUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> AssignmentEditOut:
    edit = assignment_service.replace_assignment(
        session, user, week_start, assignment_id, user_id=body.user_id
    )
    return edit_out(edit)


@router.delete("/{week_start}/assignments/{assignment_id}", status_code=204)
def remove_assignment(
    week_start: date, assignment_id: int, user: CurrentUser, session: SessionDep
) -> None:
    assignment_service.remove_assignment(session, user, week_start, assignment_id)


# --- mapping from service results to response schemas ---


def edit_out(edit: AssignmentEdit) -> AssignmentEditOut:
    return AssignmentEditOut(
        assignment=AssignmentOut(
            id=edit.assignment.id,
            shift_id=edit.shift.id,
            user_id=edit.user.id,
            user_name=edit.user.name,
            starts_at=edit.shift.starts_at,
            ends_at=edit.shift.ends_at,
        ),
        warnings=[WarningOut(code=w.code, message=w.message) for w in edit.warnings],
    )


def schedule_out(view: ScheduleView) -> ScheduleOut:
    shifts = {shift.id: shift for shift in view.shifts}
    assigned: dict[int, int] = {}
    for item in view.assignments:
        assigned[item.shift_id] = assigned.get(item.shift_id, 0) + 1
    return ScheduleOut(
        id=view.schedule.id,
        week_start=view.schedule.week_start,
        status=view.schedule.status,
        published_at=view.schedule.published_at,
        assignments=[
            AssignmentOut(
                id=item.id,
                shift_id=item.shift_id,
                user_id=item.user_id,
                user_name=view.users[item.user_id].name,
                starts_at=shifts[item.shift_id].starts_at,
                ends_at=shifts[item.shift_id].ends_at,
            )
            for item in view.assignments
        ],
        shifts=[
            ShiftCoverageOut(
                shift_id=shift.id,
                name=shift.name,
                starts_at=shift.starts_at,
                ends_at=shift.ends_at,
                required_staff=shift.required_staff,
                assigned_count=assigned.get(shift.id, 0),
                unfilled_count=max(shift.required_staff - assigned.get(shift.id, 0), 0),
            )
            for shift in view.shifts
        ],
    )


def generate_out(generated: GeneratedSchedule) -> ScheduleGenerateOut:
    proposal = generated.proposal
    names = {employee.id: employee.name for employee in proposal.employees}
    result = proposal.result
    return ScheduleGenerateOut(
        schedule=schedule_out(generated.view),
        unfilled=[
            UnfilledSlotOut(
                shift_id=slot.shift_id,
                required=slot.required,
                assigned=slot.assigned,
                missing=slot.missing,
                reasons=[
                    ReasonOut(
                        user_id=reason.employee_id,
                        user_name=names[reason.employee_id],
                        constraint=reason.constraint,
                        shift_id=reason.shift_id,
                    )
                    for reason in slot.reasons
                ],
                sentence=sentence,
            )
            for slot, sentence in zip(result.unfilled, proposal.sentences, strict=True)
        ],
        score=ScoreOut(
            filled=result.score.filled,
            preferred=result.score.preferred,
            spread_minutes=result.score.spread_minutes,
            value=result.score.value,
        ),
        complete=result.complete,
        steps=result.steps,
    )
