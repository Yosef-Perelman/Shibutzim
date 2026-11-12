from typing import Any

from pydantic import BaseModel, Field

from app.assistant.context import ToolContext
from app.assistant.tools.base import Tool
from app.core.enums import Role
from app.services import handbook_service


class SearchPolicyArguments(BaseModel):
    query: str = Field(min_length=1, max_length=300, description="The question, in plain words")


def run(context: ToolContext, arguments: SearchPolicyArguments) -> dict[str, Any]:
    matches = handbook_service.search_policy(context.session, context.llm, arguments.query)
    return {
        "matches": [
            {"section_title": item.section_title, "content": item.content, "score": item.score}
            for item in matches
        ]
    }


TOOL = Tool(
    name="search_policy",
    roles=frozenset({Role.employee, Role.manager}),
    writes=False,
    arguments=SearchPolicyArguments,
    run=run,
)
