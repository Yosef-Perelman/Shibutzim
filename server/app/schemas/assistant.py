"""Assistant chat request and response. The client sends the whole history each time."""

from datetime import date
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

MAX_MESSAGES = 20
MAX_MESSAGE_CHARACTERS = 2000


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARACTERS)


class ChatIn(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=MAX_MESSAGES)

    @model_validator(mode="after")
    def last_message_is_from_the_user(self) -> Self:
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be from the user")
        return self


class ToolCallOut(BaseModel):
    """What the assistant looked up: the tool and its arguments, not the result."""

    name: str
    args: dict[str, Any]


class DayOffOut(BaseModel):
    user_id: int
    name: str
    day: date


class ProposedShiftOut(BaseModel):
    shift_id: int
    date: date
    weekday: str
    name: str
    start: str
    end: str
    people: list[str]


class ProposalOut(BaseModel):
    """A schedule the manager may confirm. Confirming calls the normal generate endpoint with
    `week_start` and `unavailable`; nothing is saved until then."""

    type: Literal["schedule_draft"]
    week_start: date
    unavailable: list[DayOffOut]
    summary: str
    filled: int
    required: int
    replaces_draft: bool
    assignments: list[ProposedShiftOut]
    unfilled: list[str]


class ChatOut(BaseModel):
    message: str
    citations: list[str]
    tool_calls: list[ToolCallOut]
    proposal: ProposalOut | None
