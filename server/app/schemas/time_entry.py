from datetime import datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.core.enums import TimeEntrySource

NOTE_MAX_LENGTH = 500


class TimeEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    clock_in: datetime
    clock_out: datetime | None
    source: TimeEntrySource
    created_by: int
    note: str | None


class TimeEntryCreate(BaseModel):
    """A manager's manual entry; always closed. Datetimes must carry a UTC offset."""

    user_id: int
    clock_in: AwareDatetime
    clock_out: AwareDatetime
    note: str | None = Field(default=None, max_length=NOTE_MAX_LENGTH)


class TimeEntryUpdate(BaseModel):
    """A partial correction. Only the fields sent change; times cannot be cleared."""

    model_config = ConfigDict(extra="forbid")

    clock_in: AwareDatetime | None = None
    clock_out: AwareDatetime | None = None
    note: str | None = Field(default=None, max_length=NOTE_MAX_LENGTH)

    @model_validator(mode="after")
    def check_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("send at least one of clock_in, clock_out, note")
        for name in ("clock_in", "clock_out"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared")
        return self
