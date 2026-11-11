"""The shape every tool has, and the argument model the date-range tools share."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.assistant.context import ToolContext
from app.assistant.llm import ToolDefinition
from app.assistant.prompts import load_prompt
from app.core.enums import Role


class DateRangeArguments(BaseModel):
    """`from` and `to` as the model sees them; both days are included."""

    from_day: date = Field(alias="from", description="First day, YYYY-MM-DD, included")
    to_day: date = Field(alias="to", description="Last day, YYYY-MM-DD, included")


@dataclass(frozen=True)
class Tool:
    """A function the model may call. `writes` tools return a proposal and never write."""

    name: str
    roles: frozenset[Role]
    writes: bool
    arguments: type[BaseModel]
    run: Callable[[ToolContext, Any], dict[str, Any]]

    def definition(self) -> ToolDefinition:
        """What the model sees; the description is a prompt file named after the tool."""
        return ToolDefinition(
            name=self.name,
            description=load_prompt(f"tools/{self.name}.md"),
            parameters=self.arguments.model_json_schema(),
        )
