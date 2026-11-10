"""Input and output types of the pay calculation (glossary: pay breakdown)."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.pay.rules import OvertimeTier


@dataclass(frozen=True)
class Entry:
    """A closed time entry reduced to what pay needs. Services build these from `TimeEntry` rows."""

    clock_in: datetime
    clock_out: datetime


@dataclass(frozen=True)
class TierLine:
    """Seconds of one work day that fell into one tier, and what they earned."""

    tier: OvertimeTier
    seconds: int
    hours: Decimal
    amount: Decimal


@dataclass(frozen=True)
class DayBreakdown:
    work_day: date
    seconds: int
    hours: Decimal
    lines: tuple[TierLine, ...]
    amount: Decimal


@dataclass(frozen=True)
class PayBreakdown:
    days: tuple[DayBreakdown, ...]
    seconds: int
    hours: Decimal
    amount: Decimal
