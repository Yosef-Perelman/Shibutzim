from typing import Any
from zoneinfo import ZoneInfo

from app.assistant.context import ToolContext
from app.assistant.formatting import shift_fields
from app.assistant.tools.base import DateRangeArguments, Tool
from app.config import get_settings
from app.core.enums import Role
from app.services import assignment_service
from app.services.assignment_service import AssignedShift


def run(context: ToolContext, arguments: DateRangeArguments) -> dict[str, Any]:
    rows = assignment_service.list_assigned_shifts(
        context.session, context.user, from_day=arguments.from_day, to_day=arguments.to_day
    )
    zone = get_settings().tz
    return {"count": len(rows), "shifts": [describe(row, zone) for row in rows]}


def describe(row: AssignedShift, zone: ZoneInfo) -> dict[str, Any]:
    fields = shift_fields(row.shift, zone)
    ends_next_day = (
        row.shift.ends_at.astimezone(zone).date() > row.shift.starts_at.astimezone(zone).date()
    )
    return {**fields, "ends_next_day": ends_next_day, "schedule": row.schedule_status.value}


TOOL = Tool(
    name="get_my_shifts",
    roles=frozenset({Role.employee}),
    writes=False,
    arguments=DateRangeArguments,
    run=run,
)
