"""The registry: which tools a role sees, and where their descriptions come from."""

import json

import pytest

from app.assistant.prompts import load_prompt
from app.assistant.tools import registry
from app.core.enums import Role

EMPLOYEE_TOOLS = {"get_my_shifts", "get_my_hours", "explain_pay", "search_policy"}


def names(role: Role) -> set[str]:
    return {tool.name for tool in registry.tools_for_role(role)}


def test_an_employee_sees_the_four_employee_tools():
    assert names(Role.employee) == EMPLOYEE_TOOLS


def test_a_manager_shares_the_policy_search_but_not_the_personal_tools():
    manager_tools = names(Role.manager)

    assert "search_policy" in manager_tools
    assert not manager_tools & {"get_my_shifts", "get_my_hours", "explain_pay"}


def test_get_tool_finds_a_tool_by_name_and_returns_none_for_an_unknown_one():
    assert registry.get_tool("explain_pay").name == "explain_pay"
    assert registry.get_tool("drop_database") is None


@pytest.mark.parametrize("role", list(Role))
def test_every_definition_has_a_description_from_a_file_and_a_json_schema(role: Role):
    for definition in registry.definitions_for_role(role):
        assert len(definition.description) > 40
        assert definition.description == load_prompt(f"tools/{definition.name}.md")
        assert definition.parameters["type"] == "object"
        json.dumps(definition.parameters)


def test_the_date_tools_take_from_and_to_as_the_model_sees_them():
    for name in ("get_my_shifts", "get_my_hours", "explain_pay"):
        schema = registry.get_tool(name).definition().parameters

        assert set(schema["properties"]) == {"from", "to"}
        assert set(schema["required"]) == {"from", "to"}


def test_search_policy_takes_a_query():
    schema = registry.get_tool("search_policy").definition().parameters

    assert set(schema["properties"]) == {"query"}


def test_load_prompt_reads_a_file_and_fails_loudly_for_a_missing_one():
    assert load_prompt("tools/get_my_shifts.md").strip()
    with pytest.raises(FileNotFoundError):
        load_prompt("tools/does_not_exist.md")


def test_load_prompt_refuses_to_leave_the_prompts_folder():
    with pytest.raises(ValueError):
        load_prompt("../config.py")


MANAGER_TOOLS = {"who_is_available", "get_team_hours", "generate_schedule_draft", "search_policy"}


def test_a_manager_sees_the_manager_tools_and_the_policy_search():
    assert names(Role.manager) == MANAGER_TOOLS


def test_an_employee_never_sees_a_manager_tool():
    assert not names(Role.employee) & {
        "who_is_available",
        "get_team_hours",
        "generate_schedule_draft",
    }


def test_only_the_schedule_draft_tool_is_a_write_tool():
    writers = {tool.name for tool in registry.ALL_TOOLS if tool.writes}

    assert writers == {"generate_schedule_draft"}


def test_the_manager_tools_declare_their_arguments():
    who = registry.get_tool("who_is_available").definition().parameters
    team = registry.get_tool("get_team_hours").definition().parameters
    draft = registry.get_tool("generate_schedule_draft").definition().parameters

    assert set(who["properties"]) == {"shift_id", "day", "shift"}
    assert "required" not in who
    assert set(team["properties"]) == {"from", "to"}
    assert set(draft["properties"]) == {"week_start", "unavailable"}
    assert draft["required"] == ["week_start"]
