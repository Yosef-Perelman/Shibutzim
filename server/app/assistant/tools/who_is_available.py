from datetime import date
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from app.assistant.context import ToolContext
from app.assistant.formatting import shift_fields
from app.assistant.tools.base import Tool
from app.config import get_settings
from app.core.enums import AvailabilityStatus, Role
from app.core.errors import ErrorCode, NotFound, ValidationFailed
from app.core.time import week_start
from app.services import availability_service, shift_service


class WhoIsAvailableArguments(BaseModel):
    shift_id: int | None = Field(default=None, description="The id of the shift, if known")
    day: date | None = Field(default=None, description="The day of the shift, YYYY-MM-DD")
    shift: str | None = Field(
        default=None, max_length=120, description="Part of the shift's name, e.g. morning"
    )

    @model_validator(mode="after")
    def needs_an_id_or_a_day(self) -> Self:
        if self.shift_id is None and self.day is None:
            raise ValueError(
                "give either shift_id or day (with the shift name if the day has several)"
            )
        return self


def run(context: ToolContext, arguments: WhoIsAvailableArguments) -> dict[str, Any]:
    shift_id = arguments.shift_id
    shift = (
        shift_service.get_shift(context.session, context.user, shift_id)
        if shift_id is not None
        else find_shift(context, arguments)
    )
    answers = availability_service.list_for_shift(context.session, context.user, shift.id)
    names = {
        status: [answer.user.name for answer in answers if answer.status is status]
        for status in AvailabilityStatus
    }
    return {
        "shift": {
            "id": shift.id,
            **shift_fields(shift, get_settings().tz),
            "required_staff": shift.required_staff,
        },
        "preferred": names[AvailabilityStatus.preferred],
        "available": names[AvailabilityStatus.available],
        "unavailable": names[AvailabilityStatus.unavailable],
    }


def find_shift(context: ToolContext, arguments: WhoIsAvailableArguments):
    """The one shift that starts on the day and whose name contains the given text."""
    day, wanted = arguments.day, (arguments.shift or "").strip().casefold()
    zone = get_settings().tz
    of_the_week = shift_service.list_shifts(context.session, context.user, week_start(day))
    on_the_day = [s for s in of_the_week if s.starts_at.astimezone(zone).date() == day]
    matching = [s for s in on_the_day if wanted in s.name.casefold()]
    if len(matching) == 1:
        return matching[0]
    if not matching:
        raise NotFound(ErrorCode.shift_not_found, f"There is no matching shift on {day}.")
    names = ", ".join(sorted(s.name for s in matching))
    raise ValidationFailed(
        ErrorCode.validation_error, f"Several shifts match on {day}: {names}. Ask which one."
    )


TOOL = Tool(
    name="who_is_available",
    roles=frozenset({Role.manager}),
    writes=False,
    arguments=WhoIsAvailableArguments,
    run=run,
)
