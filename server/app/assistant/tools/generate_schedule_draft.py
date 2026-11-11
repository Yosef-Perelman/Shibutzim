"""The write tool: runs the solver in dry-run mode and returns a proposal; it never writes."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.assistant.context import ToolContext
from app.assistant.formatting import shift_fields
from app.assistant.tools.base import Tool
from app.config import get_settings
from app.core.enums import Role, ScheduleStatus
from app.core.errors import Conflict, ErrorCode, NotFound
from app.services import schedule_service, user_service
from app.services.schedule_service import DayOff, Proposal

NOTE = "This is only a proposal. Nothing is saved until the manager confirms it in the app."


class DayOffArguments(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="The employee's name as said")
    day: date = Field(description="The day off, YYYY-MM-DD, inside the week")


class GenerateScheduleDraftArguments(BaseModel):
    week_start: date = Field(description="The Sunday that starts the week, YYYY-MM-DD")
    unavailable: list[DayOffArguments] = Field(default_factory=list, max_length=50)


def run(context: ToolContext, arguments: GenerateScheduleDraftArguments) -> dict[str, Any]:
    session, manager, week = context.session, context.user, arguments.week_start
    existing = current_status(context, week)
    if existing is ScheduleStatus.published:
        raise Conflict(ErrorCode.schedule_published, f"The week of {week} is already published.")
    days_off = [
        (user_service.find_active_employee(session, manager, item.name), item.day)
        for item in arguments.unavailable
    ]
    proposal = schedule_service.propose_schedule(
        session, manager, week, unavailable=[DayOff(user.id, day) for user, day in days_off]
    )
    replaces = existing is ScheduleStatus.draft
    summary = summarize(proposal)
    required = sum(shift.required_staff for shift in proposal.shifts)
    filled = proposal.result.score.filled
    applied = [{"name": user.name, "day": day.isoformat()} for user, day in days_off]
    return {
        "summary": summary,
        "filled": filled,
        "required": required,
        "unfilled": proposal.sentences,
        "days_off_applied": applied,
        "replaces_draft": replaces,
        "note": NOTE,
        "proposal": {
            "type": "schedule_draft",
            "week_start": week.isoformat(),
            "unavailable": [
                {"user_id": user.id, "name": user.name, "day": day.isoformat()}
                for user, day in days_off
            ],
            "summary": summary,
            "filled": filled,
            "required": required,
            "replaces_draft": replaces,
            "assignments": describe_assignments(proposal),
            "unfilled": proposal.sentences,
        },
    }


def current_status(context: ToolContext, week: date) -> ScheduleStatus | None:
    """The status of the week's schedule, or None if it has none yet."""
    try:
        view = schedule_service.get_schedule(context.session, context.user, week)
    except NotFound:
        return None
    return view.schedule.status


def summarize(proposal: Proposal) -> str:
    required = sum(shift.required_staff for shift in proposal.shifts)
    text = f"{proposal.result.score.filled} of {required} positions filled."
    short = len(proposal.result.unfilled)
    if short == 0:
        return f"{text} Every shift is fully staffed."
    verb = "shift is" if short == 1 else "shifts are"
    return f"{text} {short} {verb} short of staff."


def describe_assignments(proposal: Proposal) -> list[dict[str, Any]]:
    names = {employee.id: employee.name for employee in proposal.employees}
    people: dict[int, list[str]] = {shift.id: [] for shift in proposal.shifts}
    for assignment in proposal.result.assignments:
        people[assignment.shift_id].append(names[assignment.employee_id])
    zone = get_settings().tz
    return [
        {"shift_id": shift.id, **shift_fields(shift, zone), "people": sorted(people[shift.id])}
        for shift in proposal.shifts
    ]


TOOL = Tool(
    name="generate_schedule_draft",
    roles=frozenset({Role.manager}),
    writes=True,
    arguments=GenerateScheduleDraftArguments,
    run=run,
)
