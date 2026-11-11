from typing import Any

from app.assistant.context import ToolContext
from app.assistant.tools.base import DateRangeArguments, Tool
from app.core.enums import Role
from app.pay import DayBreakdown
from app.schemas.pay import display_hours
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
        "total_hours": str(display_hours(breakdown.seconds)),
        "regular_hours": str(display_hours(breakdown.seconds - overtime)),
        "overtime_hours": str(display_hours(overtime)),
        "open_entries": report.open_entries,
        "days": [
            {
                "date": day.work_day.isoformat(),
                "hours": str(display_hours(day.seconds)),
                "overtime_hours": str(display_hours(overtime_seconds(day))),
            }
            for day in breakdown.days
        ],
    }


def overtime_seconds(day: DayBreakdown) -> int:
    """Seconds of the day paid above the base rate."""
    return sum(line.seconds for line in day.lines if line.tier.multiplier > 1)


TOOL = Tool(
    name="get_my_hours",
    roles=frozenset({Role.employee}),
    writes=False,
    arguments=DateRangeArguments,
    run=run,
)
