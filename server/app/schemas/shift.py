from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    name: str
    week_start: date
    starts_at: datetime
    ends_at: datetime
    required_staff: int


class ShiftGenerate(BaseModel):
    """Which week to generate shifts for: its Sunday."""

    week_start: date


class ShiftGenerateOut(BaseModel):
    week_start: date
    created: int
    shifts: list[ShiftOut]
