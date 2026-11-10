"""Pure pay calculation (product-definition §5.4, §6.1; architecture §6.3).

Durations are integer seconds; money is `Decimal`. Each tier line is rounded to the cent with
ROUND_HALF_UP and every total is the sum of its lines, so a breakdown always adds up like a payslip
(plan 001, open question 7). Hours are never rounded.
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from app.core.time import duration_seconds, work_day
from app.pay.breakdown import DayBreakdown, Entry, PayBreakdown, TierLine
from app.pay.rules import SECONDS_PER_HOUR, OvertimeTier, PayRules

CENT = Decimal("0.01")
ZERO_AMOUNT = Decimal("0.00")


def calculate(
    entries: Iterable[Entry], hourly_rate: Decimal, rules: PayRules, tz: ZoneInfo
) -> PayBreakdown:
    """Group entries by work day, apply the tiers to each day's total, and sum.

    Raises `ValueError` for impossible input (naive datetimes, clock_out not after clock_in,
    negative rate); the calling service converts it to a domain error.
    """
    if hourly_rate < 0:
        raise ValueError("hourly_rate must not be negative")

    seconds_by_day: dict[date, int] = defaultdict(int)
    for entry in entries:
        seconds_by_day[work_day(entry.clock_in, tz)] += entry_seconds(entry)

    days = tuple(
        day_breakdown(day, seconds, hourly_rate, rules)
        for day, seconds in sorted(seconds_by_day.items())
    )
    total_seconds = sum(day.seconds for day in days)
    return PayBreakdown(
        days=days,
        seconds=total_seconds,
        hours=hours_from_seconds(total_seconds),
        amount=sum((day.amount for day in days), ZERO_AMOUNT),
    )


def entry_seconds(entry: Entry) -> int:
    seconds = duration_seconds(entry.clock_in, entry.clock_out)
    if seconds <= 0:
        raise ValueError("clock_out must be after clock_in")
    return seconds


def day_breakdown(day: date, seconds: int, hourly_rate: Decimal, rules: PayRules) -> DayBreakdown:
    """Walk the tiers over the day's total; tiers the day never reaches produce no line."""
    lines = tuple(
        line for tier in rules.tiers if (line := tier_line(tier, seconds, hourly_rate)) is not None
    )
    return DayBreakdown(
        work_day=day,
        seconds=seconds,
        hours=hours_from_seconds(seconds),
        lines=lines,
        amount=sum((line.amount for line in lines), ZERO_AMOUNT),
    )


def tier_line(tier: OvertimeTier, day_seconds: int, hourly_rate: Decimal) -> TierLine | None:
    upper = day_seconds if tier.to_second is None else min(day_seconds, tier.to_second)
    seconds = max(0, upper - tier.from_second)
    if seconds == 0:
        return None
    raw_amount = hourly_rate * tier.multiplier * Decimal(seconds) / SECONDS_PER_HOUR
    return TierLine(
        tier=tier,
        seconds=seconds,
        hours=hours_from_seconds(seconds),
        amount=raw_amount.quantize(CENT, rounding=ROUND_HALF_UP),
    )


def hours_from_seconds(seconds: int) -> Decimal:
    return Decimal(seconds) / Decimal(SECONDS_PER_HOUR)
