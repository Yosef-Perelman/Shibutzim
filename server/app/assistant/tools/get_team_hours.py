from typing import Any

from app.assistant.context import ToolContext
from app.assistant.formatting import hours_text, overtime_seconds
from app.assistant.tools.base import DateRangeArguments, Tool
from app.core.enums import Role
from app.services import pay_service
from app.services.pay_service import UserPay


def run(context: ToolContext, arguments: DateRangeArguments) -> dict[str, Any]:
    reports = pay_service.get_team_pay(
        context.session, context.user, from_day=arguments.from_day, to_day=arguments.to_day
    )
    worked = [report for report in reports if report.breakdown.seconds or report.open_entries]
    return {
        "from": arguments.from_day.isoformat(),
        "to": arguments.to_day.isoformat(),
        "total_hours": hours_text(sum(report.breakdown.seconds for report in worked)),
        "people": [describe(report) for report in worked],
    }


def describe(report: UserPay) -> dict[str, Any]:
    return {
        "user_id": report.user.id,
        "name": report.user.name,
        "hours": hours_text(report.breakdown.seconds),
        "overtime_hours": hours_text(sum(overtime_seconds(day) for day in report.breakdown.days)),
        "open_entries": report.open_entries,
    }


TOOL = Tool(
    name="get_team_hours",
    roles=frozenset({Role.manager}),
    writes=False,
    arguments=DateRangeArguments,
    run=run,
)
