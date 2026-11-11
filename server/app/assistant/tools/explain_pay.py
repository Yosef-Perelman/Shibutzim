from typing import Any

from app.assistant.context import ToolContext
from app.assistant.formatting import hours_text
from app.assistant.tools.base import DateRangeArguments, Tool
from app.core.enums import Role
from app.pay import DayBreakdown, TierLine
from app.services import pay_service

PERCENT = 100
CURRENCY = "ILS"


def run(context: ToolContext, arguments: DateRangeArguments) -> dict[str, Any]:
    report = pay_service.get_pay(
        context.session, context.user, from_day=arguments.from_day, to_day=arguments.to_day
    )
    breakdown = report.breakdown
    return {
        "from": arguments.from_day.isoformat(),
        "to": arguments.to_day.isoformat(),
        "currency": CURRENCY,
        "hourly_rate": str(report.user.hourly_rate),
        "total_hours": hours_text(breakdown.seconds),
        "total_amount": str(breakdown.amount),
        "open_entries": report.open_entries,
        "days": [describe_day(day) for day in breakdown.days],
    }


def describe_day(day: DayBreakdown) -> dict[str, Any]:
    return {
        "date": day.work_day.isoformat(),
        "hours": hours_text(day.seconds),
        "amount": str(day.amount),
        "tiers": [describe_tier(line) for line in day.lines if line.seconds > 0],
    }


def describe_tier(line: TierLine) -> dict[str, Any]:
    return {
        "rate_percent": int(line.tier.multiplier * PERCENT),
        "hours": hours_text(line.seconds),
        "amount": str(line.amount),
    }


TOOL = Tool(
    name="explain_pay",
    roles=frozenset({Role.employee}),
    writes=False,
    arguments=DateRangeArguments,
    run=run,
)
