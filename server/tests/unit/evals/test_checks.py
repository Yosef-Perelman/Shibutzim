"""The eval checkers: pure functions that compare one assistant run with what its case expects."""

import pytest

from app.assistant.agent import AgentReply, ToolCallInfo
from evals.checks import appears, check_case, resolve_path
from evals.types import EvalCase, Fact


def reply(text="ok", tools=(), citations=(), proposal=None) -> AgentReply:
    return AgentReply(
        text=text,
        citations=list(citations),
        tool_calls=[ToolCallInfo(name, {}) for name in tools],
        proposal=proposal,
    )


def case(**overrides) -> EvalCase:
    return EvalCase(id="c", persona="Noa Katz", question="q", **overrides)


# --- appears: a value from a tool result must show up in the answer ---


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("3198.13", "You earned ₪3,198.13 this month."),
        ("3198.13", "Total: 3198.13"),
        ("8.00", "You worked 8 hours."),
        ("8.00", "You worked 8.0 hours."),
        ("8.50", "You worked 8.5 hours."),
        ("8.50", "You worked 8.50 hours."),
        ("125", "paid at 125% of your rate"),
        ("Morning", "your morning shift"),
    ],
)
def test_appears_accepts_the_usual_ways_of_writing_a_value(value: str, text: str):
    assert appears(value, text)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("8.00", "You worked 18 hours."),
        ("8.00", "You worked 8.25 hours."),
        ("8.00", "You worked 80 hours."),
        ("8.50", "You worked 8.55 hours."),
        ("3198.13", "You earned 3198.14."),
        ("Morning", "your evening shift"),
    ],
)
def test_appears_rejects_a_different_number_or_text(value: str, text: str):
    assert not appears(value, text)


@pytest.mark.parametrize(
    "text",
    [
        "You earned ₪0.00 last month.",
        "You earned 0 last month.",
        "You earned nothing last month.",
        "There was no pay last month.",
        "You did not work last month, so zero.",
    ],
)
def test_a_zero_value_may_be_said_in_words(text: str):
    assert appears("0.00", text)


def test_a_zero_value_is_not_found_in_an_answer_that_only_has_other_numbers():
    assert not appears("0.00", "You earned ₪250.00 last month.")


# --- resolve_path ---


def test_resolve_path_walks_dicts_and_list_indexes():
    result = {"days": [{"hours": "8.00"}, {"hours": "9.00"}], "total": "17.00"}

    assert resolve_path(result, "total") == "17.00"
    assert resolve_path(result, "days.1.hours") == "9.00"


@pytest.mark.parametrize("path", ["missing", "days.5.hours", "days.x", "total.deeper"])
def test_resolve_path_returns_none_for_a_missing_path(path: str):
    assert resolve_path({"days": [{"hours": "8.00"}], "total": "17.00"}, path) is None


# --- tools ---


def test_a_run_that_does_what_the_case_expects_has_no_failures():
    expected = case(expected_tools=("get_my_hours",), forbidden_tools=("get_team_hours",))

    assert check_case(expected, reply(tools=["get_my_hours"]), {}) == []


def test_a_missing_expected_tool_is_a_failure():
    failures = check_case(case(expected_tools=("get_my_hours",)), reply(tools=[]), {})

    assert failures == ["expected a call to get_my_hours"]


def test_a_forbidden_tool_is_a_failure():
    failures = check_case(
        case(forbidden_tools=("get_team_hours",)), reply(tools=["get_team_hours"]), {}
    )

    assert failures == ["must not call get_team_hours"]


def test_too_many_tool_calls_is_a_failure():
    failures = check_case(case(max_tool_calls=0), reply(tools=["search_policy"]), {})

    assert failures == ["made 1 tool calls, at most 0 allowed"]


# --- facts ---


def results(tool: str, *contents: dict) -> dict[str, list[dict]]:
    return {tool: list(contents)}


def test_a_fact_from_the_first_result_must_appear_in_the_answer():
    expected = case(facts=(Fact("get_my_hours", "total_hours"),))

    passing = check_case(
        expected,
        reply("You worked 8 hours.", ["get_my_hours"]),
        results("get_my_hours", {"total_hours": "8.00"}),
    )
    failing = check_case(
        expected,
        reply("You worked 9 hours.", ["get_my_hours"]),
        results("get_my_hours", {"total_hours": "8.00"}),
    )

    assert passing == []
    assert failing == ["the answer does not say get_my_hours.total_hours = 8.00"]


def test_every_flag_requires_the_value_from_every_result():
    expected = case(facts=(Fact("explain_pay", "total_amount", every=True),))
    both = results("explain_pay", {"total_amount": "100.00"}, {"total_amount": "200.00"})

    assert check_case(expected, reply("This month 100 and last month 200."), both) == []
    assert check_case(expected, reply("This month 100."), both) == [
        "the answer does not say explain_pay.total_amount = 200.00"
    ]


def test_a_fact_whose_tool_never_ran_is_a_failure():
    expected = case(facts=(Fact("get_my_hours", "total_hours"),))

    assert check_case(expected, reply("8 hours"), {}) == [
        "no result from get_my_hours to check against"
    ]


def test_an_optional_fact_is_skipped_when_the_path_is_missing():
    expected = case(facts=(Fact("get_my_shifts", "shifts.0.start", optional=True),))

    assert check_case(expected, reply("No shifts."), results("get_my_shifts", {"shifts": []})) == []


def test_a_required_fact_with_a_missing_path_is_a_failure():
    expected = case(facts=(Fact("get_my_shifts", "shifts.0.start"),))

    failures = check_case(expected, reply("No shifts."), results("get_my_shifts", {"shifts": []}))

    assert failures == ["get_my_shifts has no value at shifts.0.start"]


# --- citations ---


def test_a_required_citation_must_be_among_the_citations():
    expected = case(citation="Shift swaps")

    assert check_case(expected, reply(citations=["Shift swaps"]), {}) == []
    assert check_case(expected, reply(citations=["Breaks"]), {}) == [
        "expected a citation of the Shift swaps section"
    ]


def test_no_citation_means_no_section_was_named():
    expected = case(no_citation=True)

    assert check_case(expected, reply(citations=[]), {}) == []
    assert check_case(expected, reply(citations=["Breaks"]), {}) == [
        "must not cite a section, but cited Breaks"
    ]


# --- text ---


def test_must_contain_must_contain_any_and_must_not_contain():
    expected = case(
        must_contain=("125",),
        must_contain_any=("handbook", "policy"),
        must_not_contain=("42.50",),
    )

    assert check_case(expected, reply("125% by the handbook"), {}) == []
    assert check_case(expected, reply("by the handbook, 42.50 per hour"), {}) == [
        "the answer does not contain '125'",
        "the answer mentions '42.50'",
    ]
    assert check_case(expected, reply("125 percent"), {}) == [
        "the answer contains none of: handbook, policy"
    ]


def test_text_checks_ignore_case_and_thousands_separators():
    expected = case(must_contain=("Handbook",), must_not_contain=("12345",))

    assert check_case(expected, reply("see the HANDBOOK, 12,345 total"), {}) == [
        "the answer mentions '12345'"
    ]


def test_an_empty_answer_is_a_failure():
    assert check_case(case(), reply(""), {}) == ["the answer is empty"]


# --- proposals ---

PROPOSAL = {
    "type": "schedule_draft",
    "week_start": "2026-03-15",
    "unavailable": [{"user_id": 3, "name": "Noa Katz", "day": "2026-03-17"}],
}


def test_a_proposal_is_expected_with_the_right_days_off():
    expected = case(expects_proposal=True, proposal_days_off=(("Noa Katz", "Tuesday"),))

    assert check_case(expected, reply(proposal=PROPOSAL), {}) == []


def test_a_missing_proposal_is_a_failure():
    assert check_case(case(expects_proposal=True), reply(), {}) == ["expected a schedule proposal"]


def test_a_proposal_nobody_asked_for_is_a_failure():
    assert check_case(case(), reply(proposal=PROPOSAL), {}) == [
        "did not expect a schedule proposal"
    ]


def test_a_proposal_with_the_wrong_day_off_is_a_failure():
    expected = case(expects_proposal=True, proposal_days_off=(("Noa Katz", "Monday"),))

    failures = check_case(expected, reply(proposal=PROPOSAL), {})

    assert failures == [
        "days off in the proposal are [('Noa Katz', 'Tuesday')], expected [('Noa Katz', 'Monday')]"
    ]
