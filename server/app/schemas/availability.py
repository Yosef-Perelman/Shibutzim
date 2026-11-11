from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import AvailabilityStatus


class AvailabilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shift_id: int
    user_id: int
    status: AvailabilityStatus


class AvailabilityItem(BaseModel):
    shift_id: int
    status: AvailabilityStatus


class AvailabilitySet(BaseModel):
    """Answers for some shifts of one week. `user_id` is for managers answering for someone."""

    week_start: date
    user_id: int | None = None
    items: list[AvailabilityItem] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_shifts(self) -> Self:
        shift_ids = [item.shift_id for item in self.items]
        if len(set(shift_ids)) != len(shift_ids):
            raise ValueError("each shift may be answered once per request")
        return self
