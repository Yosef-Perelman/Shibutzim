"""The add-pay-rule matrix checker's decision logic (the script itself lives in .claude/skills)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / ".claude/skills/add-pay-rule/check_matrix.py"
FULL = {"at_boundary", "crossing_midnight", "split_shift", "with_overtime_tiers", "zero_hours"}


@pytest.fixture(scope="module")
def checker():
    spec = importlib.util.spec_from_file_location("check_matrix", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_complete_matrix_has_no_gaps(checker) -> None:
    assert checker.missing_cases({"night_premium": FULL}) == {}


def test_extra_cases_are_allowed(checker) -> None:
    assert checker.missing_cases({"overtime_tiers": FULL | {"9h", "exactly_8h"}}) == {}


@pytest.mark.parametrize("missing", sorted(FULL))
def test_each_required_case_is_enforced(checker, missing: str) -> None:
    gaps = checker.missing_cases({"night_premium": FULL - {missing}})

    assert gaps == {"night_premium": [missing]}


def test_every_incomplete_rule_is_reported_separately(checker) -> None:
    found = {"a": FULL, "b": FULL - {"zero_hours"}, "c": {"at_boundary"}}

    gaps = checker.missing_cases(found)

    assert set(gaps) == {"b", "c"}
    assert gaps["c"] == ["crossing_midnight", "split_shift", "with_overtime_tiers", "zero_hours"]


def test_a_named_rule_without_any_test_fails_with_all_five_cases(checker) -> None:
    gaps = checker.missing_cases({"overtime_tiers": FULL}, rules=["night_premium"])

    assert gaps == {"night_premium": list(checker.REQUIRED_CASES)}


def test_naming_a_complete_rule_ignores_incomplete_others(checker) -> None:
    found = {"good": FULL, "bad": set()}

    assert checker.missing_cases(found, rules=["good"]) == {}


def test_the_required_cases_match_the_testing_rules() -> None:
    """The five ids stand for the five cases named in testing-rules.md; keep the two in step."""
    rules_doc = " ".join((SCRIPT.parents[3] / "docs/rules/testing-rules.md").read_text().split())

    assert (
        "exactly at the boundary; crossing midnight; split shift; "
        "combined with overtime tiers; zero hours"
    ) in rules_doc
