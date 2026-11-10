#!/usr/bin/env python3
"""Fail if a pay rule's test matrix lacks any of the five required cases.

Every pay rule's tests are one parametrized test marked ``@pytest.mark.pay_rule("<rule_name>")`` whose
case ids include the five names below (docs/rules/testing-rules.md, "Pay rules"). This script collects
the tests with ``pytest --collect-only -m pay_rule`` in-process, reads the rule name from the marker and
the case id from the parametrization, and reports what is missing. It needs no database.

    cd server && uv run python ../.claude/skills/add-pay-rule/check_matrix.py [rule_name ...]

With rule names it also fails for a rule that has no tests at all. Exit code: 0 = complete, 1 = a case is
missing, 2 = pytest could not collect the tests.
"""

import os
import sys
from collections import defaultdict
from pathlib import Path

REQUIRED_CASES = (
    "at_boundary",
    "crossing_midnight",
    "split_shift",
    "with_overtime_tiers",
    "zero_hours",
)
SERVER_DIR = Path(__file__).resolve().parents[3] / "server"


def missing_cases(
    found: dict[str, set[str]], rules: list[str] | None = None
) -> dict[str, list[str]]:
    """For each checked rule, the required case ids it lacks (empty result = matrix complete)."""
    checked = rules or sorted(found)
    gaps = {
        rule: [case for case in REQUIRED_CASES if case not in found.get(rule, set())]
        for rule in checked
    }
    return {rule: cases for rule, cases in gaps.items() if cases}


class Collector:
    """pytest plugin: remember (rule, case id) for every item carrying the pay_rule marker."""

    def __init__(self) -> None:
        self.found: dict[str, set[str]] = defaultdict(set)

    def pytest_collection_modifyitems(self, items) -> None:  # noqa: ANN001 – pytest hook signature
        for item in items:
            marker = item.get_closest_marker("pay_rule")
            if marker is None or not marker.args:
                continue
            callspec = getattr(item, "callspec", None)
            self.found[marker.args[0]].add(callspec.id if callspec else item.name)


def collect() -> tuple[int, dict[str, set[str]]]:
    import pytest  # imported here so the pure function above can be tested without pytest's main()

    os.chdir(SERVER_DIR)
    collector = Collector()
    args = ["--collect-only", "-q", "-m", "pay_rule", "-p", "no:cacheprovider", "tests"]
    code = pytest.main(args, plugins=[collector])
    return int(code), dict(collector.found)


def main(argv: list[str]) -> int:
    code, found = collect()
    if code not in (0, 5):  # 5 = no tests collected, handled below as "missing"
        print(f"\npytest could not collect the pay-rule tests (exit {code}).", file=sys.stderr)
        return 2

    print("\nPay-rule matrix check")
    for rule in sorted(found):
        print(f"  {rule}: {', '.join(sorted(found[rule]))}")
    if not found:
        print("  (no test is marked pay_rule)")

    gaps = missing_cases(found, argv or None)
    for rule, cases in gaps.items():
        print(f"\nFAIL {rule}: missing {', '.join(cases)}", file=sys.stderr)
    if gaps:
        return 1
    print(f"\nOK: every checked rule has all {len(REQUIRED_CASES)} required cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
