from datetime import time
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

NAME_MAX_LENGTH = 120
MAX_REQUIRED_STAFF = 100


def local_time(value: time) -> time:
    """Template times are local wall-clock times (Asia/Jerusalem), so a UTC offset is a mistake."""
    if value.tzinfo is not None:
        raise ValueError("send a local time without a UTC offset, e.g. 07:00")
    return value


LocalTime = Annotated[time, AfterValidator(local_time)]
TemplateName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX_LENGTH)
]
Weekday = Annotated[int, Field(ge=0, le=6, description="0 = Sunday")]
RequiredStaff = Annotated[int, Field(ge=1, le=MAX_REQUIRED_STAFF)]


class ShiftTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    weekday: int
    start_time: time
    end_time: time
    required_staff: int
    is_active: bool


class ShiftTemplateCreate(BaseModel):
    """A new recurring shift. An end time at or before the start time ends the next day."""

    name: TemplateName
    weekday: Weekday
    start_time: LocalTime
    end_time: LocalTime
    required_staff: RequiredStaff


class ShiftTemplateUpdate(BaseModel):
    """A partial change. Only the fields sent change; none of them can be cleared."""

    model_config = ConfigDict(extra="forbid")

    name: TemplateName | None = None
    weekday: Weekday | None = None
    start_time: LocalTime | None = None
    end_time: LocalTime | None = None
    required_staff: RequiredStaff | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("send at least one field to change")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared")
        return self
