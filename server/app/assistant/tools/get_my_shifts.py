from typing import Any
from zoneinfo import ZoneInfo

from app.assistant.context import ToolContext
from app.assistant.tools.base import DateRangeArguments, Tool
from app.config import get_settings
from app.core.enums import Role
from app.core.time import weekday_sunday_based
from app.scheduler.explain import WEEKDAY_NAMES
from app.services import assignment_service
from app.services.assignment_service import AssignedShift


def run(context: ToolContext, arguments: DateRangeArguments) -> dict[str, Any]:
    rows = assignment_service.list_assigned_shifts(
        context.session, context.user, from_day=arguments.from_day, to_day=arguments.to_day
    )
    zone = get_settings().tz
    return {"count": len(rows), "shifts": [describe(row, zone) for row in rows]}


def describe(row: AssignedShift, zone: ZoneInfo) -> dict[str, Any]:
    start = row.shift.starts_at.astimezone(zone)
    end = row.shift.ends_at.astimezone(zone)
    return {
        "date": start.date().isoformat(),
        "weekday": WEEKDAY_NAMES[weekday_sunday_based(start.date())],
        "name": row.shift.name,
        "start": f"{start:%H:%M}",
        "end": f"{end:%H:%M}",
        "ends_next_day": end.date() > start.date(),
        "schedule": row.schedule_status.value,
    }


TOOL = Tool(
    name="get_my_shifts",
    roles=frozenset({Role.employee}),
    writes=False,
    arguments=DateRangeArguments,
    run=run,
)
