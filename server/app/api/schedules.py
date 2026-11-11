from datetime import date

from fastapi import APIRouter

from app.deps import CurrentUser, SessionDep
from app.schemas.schedule import (
    AssignmentOut,
    ReasonOut,
    ScheduleGenerateOut,
    ScheduleOut,
    ScoreOut,
    ShiftCoverageOut,
    UnfilledSlotOut,
)
from app.services import schedule_service
from app.services.schedule_service import GeneratedSchedule, ScheduleView

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("/{week_start}")
def get_schedule(week_start: date, user: CurrentUser, session: SessionDep) -> ScheduleOut:
    return schedule_out(schedule_service.get_schedule(session, user, week_start))


@router.post("/{week_start}/generate")
def generate_schedule(
    week_start: date, user: CurrentUser, session: SessionDep
) -> ScheduleGenerateOut:
    return generate_out(schedule_service.generate_schedule(session, user, week_start))


# --- mapping from service results to response schemas ---


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
