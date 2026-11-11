from typing import Any

from pydantic import BaseModel, Field

from app.assistant.context import ToolContext
from app.assistant.formatting import shift_fields
from app.assistant.tools.base import Tool
from app.config import get_settings
from app.core.enums import AvailabilityStatus, Role
from app.services import availability_service, shift_service


class WhoIsAvailableArguments(BaseModel):
    shift_id: int = Field(description="The id of the shift")


def run(context: ToolContext, arguments: WhoIsAvailableArguments) -> dict[str, Any]:
    answers = availability_service.list_for_shift(context.session, context.user, arguments.shift_id)
    shift = shift_service.get_shift(context.session, context.user, arguments.shift_id)
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


TOOL = Tool(
    name="who_is_available",
    roles=frozenset({Role.manager}),
    writes=False,
    arguments=WhoIsAvailableArguments,
    run=run,
)
