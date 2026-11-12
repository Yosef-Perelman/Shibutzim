"""Every tool, and which of them a role may see (architecture §8: filtered before the model)."""

from app.assistant.llm import ToolDefinition
from app.assistant.tools import (
    explain_pay,
    generate_schedule_draft,
    get_my_hours,
    get_my_shifts,
    get_team_hours,
    search_policy,
    who_is_available,
)
from app.assistant.tools.base import Tool
from app.core.enums import Role

ALL_TOOLS: tuple[Tool, ...] = (
    get_my_shifts.TOOL,
    get_my_hours.TOOL,
    explain_pay.TOOL,
    search_policy.TOOL,
    who_is_available.TOOL,
    get_team_hours.TOOL,
    generate_schedule_draft.TOOL,
)


def get_tool(name: str) -> Tool | None:
    return next((tool for tool in ALL_TOOLS if tool.name == name), None)


def tools_for_role(role: Role) -> list[Tool]:
    return [tool for tool in ALL_TOOLS if role in tool.roles]


def definitions_for_role(role: Role) -> list[ToolDefinition]:
    """The only tool list the model ever receives."""
    return [tool.definition() for tool in tools_for_role(role)]
