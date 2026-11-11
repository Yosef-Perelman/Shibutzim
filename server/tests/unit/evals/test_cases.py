"""The fifteen eval cases themselves: shape, unique ids and coverage of every tool."""

from collections import Counter

from app.assistant.tools import registry
from evals.cases import CASES


def test_there_are_fifteen_cases_with_unique_ids():
    ids = [case.id for case in CASES]

    assert len(ids) == 15
    assert not [name for name, count in Counter(ids).items() if count > 1]


def test_every_tool_is_expected_by_at_least_one_case():
    expected = {tool for case in CASES for tool in case.expected_tools}

    assert expected == {tool.name for tool in registry.ALL_TOOLS}


def test_the_cases_cover_employees_managers_policy_refusals_and_a_proposal():
    personas = {case.persona for case in CASES}

    assert personas == {"Noa Katz", "Dana Levi"}
    assert any(case.citation for case in CASES)
    assert any(case.no_citation for case in CASES)
    assert any(case.expects_proposal for case in CASES)
    assert any(case.max_tool_calls == 0 for case in CASES)
    assert any(case.forbidden_tools for case in CASES)


def test_every_case_has_a_question_and_something_to_check():
    for case in CASES:
        assert case.question.strip()
        assert (
            case.expected_tools
            or case.facts
            or case.citation
            or case.no_citation
            or case.must_contain
            or case.must_contain_any
            or case.must_not_contain
            or case.max_tool_calls == 0
        ), case.id
