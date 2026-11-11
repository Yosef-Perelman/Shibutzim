"""Case selection and the printed table of the eval CLI (no model, no database)."""

import pytest

from evals.cases import CASES
from evals.run import format_result, format_summary, needs_handbook, parse_args, select_cases
from evals.runner import CaseResult
from evals.types import EvalCase


def test_select_cases_without_a_filter_returns_all_fifteen():
    assert [case.id for case in select_cases(None)] == [case.id for case in CASES]


def test_select_cases_keeps_the_order_asked_for():
    assert [case.id for case in select_cases("team_hours, policy_swap")] == [
        "team_hours",
        "policy_swap",
    ]


def test_select_cases_rejects_an_unknown_id():
    with pytest.raises(ValueError, match="unknown case ids: nope"):
        select_cases("team_hours,nope")


def test_the_defaults_are_cheap_no_retries_and_spaced_calls():
    args = parse_args([])

    assert args.retries == 0
    assert args.interval >= 12
    assert args.max_calls <= 100


def test_a_passing_result_is_one_line_and_a_failing_one_lists_its_reasons():
    ok = CaseResult("hours", True, [], ["get_my_hours"], "8 hours")
    bad = CaseResult("pay", False, ["expected a call to explain_pay"], [], "I don't know")

    assert format_result(ok) == "PASS  hours                  get_my_hours"
    assert format_result(bad).splitlines() == [
        "FAIL  pay                    no tools",
        "        - expected a call to explain_pay",
    ]


def test_the_summary_counts_passes_calls_and_says_when_the_run_stopped_early():
    ok = CaseResult("a", True, [], [], "x")
    bad = CaseResult("b", False, ["f"], [], "")

    assert format_summary([ok, ok], 2, 5) == "2/2 passed; 5 model calls"
    assert format_summary([ok, bad], 4, 6) == "1/4 passed, stopped after 2 of 4; 6 model calls"


def test_the_handbook_is_only_needed_by_cases_that_search_it():
    assert needs_handbook(
        [EvalCase(id="a", persona="p", question="q", expected_tools=("search_policy",))]
    )
    assert not needs_handbook([EvalCase(id="a", persona="p", question="q")])
