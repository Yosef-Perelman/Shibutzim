"""Pay response schemas. Money and hours are `Decimal`, serialized as strings.

`seconds` is the exact duration; `hours` is the same value rounded to two decimals for display only
(the calculation itself never rounds hours).
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

from app.core.enums import Role
from app.pay.rules import SECONDS_PER_HOUR

DISPLAY_HOURS = Decimal("0.01")


def display_hours(seconds: int) -> Decimal:
    return (Decimal(seconds) / SECONDS_PER_HOUR).quantize(DISPLAY_HOURS, rounding=ROUND_HALF_UP)


class TierLineOut(BaseModel):
    from_hour: Decimal
    to_hour: Decimal | None
    multiplier: Decimal
    seconds: int
    hours: Decimal
    amount: Decimal


class DayPayOut(BaseModel):
    work_day: date
    seconds: int
    hours: Decimal
    amount: Decimal
    lines: list[TierLineOut]


class PayOut(BaseModel):
    user_id: int
    from_day: date = Field(serialization_alias="from")
    to_day: date = Field(serialization_alias="to")
    days: list[DayPayOut]
    seconds: int
    hours: Decimal
    amount: Decimal
    open_entries: int


class TeamPayRow(BaseModel):
    user_id: int
    name: str
    role: Role
    hourly_rate: Decimal
    seconds: int
    hours: Decimal
    amount: Decimal
    open_entries: int


class TeamPayOut(BaseModel):
    from_day: date = Field(serialization_alias="from")
    to_day: date = Field(serialization_alias="to")
    users: list[TeamPayRow]
    seconds: int
    hours: Decimal
    amount: Decimal
