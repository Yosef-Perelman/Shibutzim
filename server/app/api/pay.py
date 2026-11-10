from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, SessionDep
from app.pay import DayBreakdown, TierLine
from app.schemas.pay import (
    DayPayOut,
    PayOut,
    TeamPayOut,
    TeamPayRow,
    TierLineOut,
    display_hours,
)
from app.services import pay_service
from app.services.pay_service import UserPay

router = APIRouter(prefix="/api/pay", tags=["pay"])

FromDay = Annotated[date, Query(alias="from", description="First work day, inclusive")]
ToDay = Annotated[date, Query(alias="to", description="Last work day, inclusive")]


@router.get("")
def get_pay(
    user: CurrentUser,
    session: SessionDep,
    from_day: FromDay,
    to_day: ToDay,
    user_id: int | None = None,
) -> PayOut:
    report = pay_service.get_pay(session, user, from_day=from_day, to_day=to_day, user_id=user_id)
    return pay_out(report, from_day, to_day)


@router.get("/team")
def get_team_pay(
    user: CurrentUser, session: SessionDep, from_day: FromDay, to_day: ToDay
) -> TeamPayOut:
    reports = pay_service.get_team_pay(session, user, from_day=from_day, to_day=to_day)
    return team_pay_out(reports, from_day, to_day)


# --- mapping from service results to response schemas ---


def tier_line_out(line: TierLine) -> TierLineOut:
    return TierLineOut(
        from_hour=line.tier.from_hour,
        to_hour=line.tier.to_hour,
        multiplier=line.tier.multiplier,
        seconds=line.seconds,
        hours=display_hours(line.seconds),
        amount=line.amount,
    )


def day_pay_out(day: DayBreakdown) -> DayPayOut:
    return DayPayOut(
        work_day=day.work_day,
        seconds=day.seconds,
        hours=display_hours(day.seconds),
        amount=day.amount,
        lines=[tier_line_out(line) for line in day.lines],
    )


def pay_out(report: UserPay, from_day: date, to_day: date) -> PayOut:
    breakdown = report.breakdown
    return PayOut(
        user_id=report.user.id,
        from_day=from_day,
        to_day=to_day,
        days=[day_pay_out(day) for day in breakdown.days],
        seconds=breakdown.seconds,
        hours=display_hours(breakdown.seconds),
        amount=breakdown.amount,
        open_entries=report.open_entries,
    )


def team_pay_out(reports: list[UserPay], from_day: date, to_day: date) -> TeamPayOut:
    rows = [
        TeamPayRow(
            user_id=report.user.id,
            name=report.user.name,
            role=report.user.role,
            hourly_rate=report.user.hourly_rate,
            seconds=report.breakdown.seconds,
            hours=display_hours(report.breakdown.seconds),
            amount=report.breakdown.amount,
            open_entries=report.open_entries,
        )
        for report in reports
    ]
    total_seconds = sum(row.seconds for row in rows)
    return TeamPayOut(
        from_day=from_day,
        to_day=to_day,
        users=rows,
        seconds=total_seconds,
        hours=display_hours(total_seconds),
        amount=sum((row.amount for row in rows), Decimal("0.00")),
    )
