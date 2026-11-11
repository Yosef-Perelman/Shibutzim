from typing import Any

from app.assistant.context import ToolContext
from app.assistant.formatting import hours_text, overtime_seconds
from app.assistant.tools.base import DateRangeArguments, Tool
from app.core.enums import Role
from app.services import pay_service


def run(context: ToolContext, arguments: DateRangeArguments) -> dict[str, Any]:
    report = pay_service.get_pay(
        context.session, context.user, from_day=arguments.from_day, to_day=arguments.to_day
    )
    breakdown = report.breakdown
    overtime = sum(overtime_seconds(day) for day in breakdown.days)
    return {
        "from": arguments.from_day.isoformat(),
        "to": arguments.to_day.isoformat(),
        "work_days": len(breakdown.days),
        "total_hours": hours_text(breakdown.seconds),
        "regular_hours": hours_text(breakdown.seconds - overtime),
        "overtime_hours": hours_text(overtime),
        "open_entries": report.open_entries,
        "days": [
            {
                "date": day.work_day.isoformat(),
                "hours": hours_text(day.seconds),
                "overtime_hours": hours_text(overtime_seconds(day)),
            }
            for day in breakdown.days
        ],
    }


TOOL = Tool(
    name="get_my_hours",
    roles=frozenset({Role.employee}),
    writes=False,
    arguments=DateRangeArguments,
    run=run,
)
