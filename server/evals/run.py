"""Run the assistant evals against the seeded development database with the real model.

    cd server && uv run python -m evals.run                 # all cases
    uv run python -m evals.run --only policy_swap,team_hours
    uv run python -m evals.run --list

Needs `GEMINI_API_KEY`, `scripts/seed.py` and `scripts/ingest_handbook.py`. Real calls are limited
by the provider, so the run spaces them apart (`--interval`), stops at `--max-calls`, never retries
a provider error and retries a failing case only with `--retries`. Tool calls are logged to the
development database like real ones. Exit code 0 means every selected case passed.
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from app.assistant.llm.provider import build_llm
from app.config import get_settings
from app.core.errors import ServiceUnavailable
from app.db import SessionLocal
from app.models import HandbookChunk
from evals.budget import BudgetedLLM
from evals.cases import CASES
from evals.runner import CaseResult, run_cases
from evals.types import EvalCase

DEFAULT_INTERVAL_SECONDS = 13.0  # under 5 calls a minute: the free tier allows 5 per minute per model
DEFAULT_MAX_CALLS = 80


def select_cases(only: str | None) -> list[EvalCase]:
    """All cases, or the comma-separated ids given; an unknown id is an error."""
    if not only:
        return list(CASES)
    wanted = [item.strip() for item in only.split(",") if item.strip()]
    by_id = {case.id: case for case in CASES}
    unknown = [item for item in wanted if item not in by_id]
    if unknown:
        raise ValueError(f"unknown case ids: {', '.join(unknown)}")
    return [by_id[item] for item in wanted]


def format_result(result: CaseResult) -> str:
    """One line for the case and one indented line for each reason it failed."""
    mark = "PASS" if result.passed else "FAIL"
    tools = ", ".join(result.tools) or "no tools"
    lines = [f"{mark}  {result.case_id:<22} {tools}"]
    lines += [f"        - {failure}" for failure in result.failures]
    return "\n".join(lines)


def format_summary(results: Sequence[CaseResult], selected: int, calls: int) -> str:
    passed = sum(result.passed for result in results)
    stopped = f", stopped after {len(results)} of {selected}" if len(results) < selected else ""
    return f"{passed}/{selected} passed{stopped}; {calls} model calls"


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the assistant evals.")
    parser.add_argument("--only", help="comma-separated case ids")
    parser.add_argument("--list", action="store_true", help="list the case ids and exit")
    parser.add_argument("--retries", type=int, default=0, help="retries of a failing case")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list:
        print("\n".join(f"{case.id:<22} {case.persona}: {case.question}" for case in CASES))
        return 0
    try:
        cases = select_cases(args.only)
        llm = build_llm(get_settings())
    except (ValueError, ServiceUnavailable) as error:
        print(f"Cannot run the evals: {getattr(error, 'message', error)}", file=sys.stderr)
        return 2
    budgeted = BudgetedLLM(llm, max_calls=args.max_calls, min_interval_seconds=args.interval)
    with SessionLocal() as session:
        if needs_handbook(cases) and not session.scalar(select(func.count(HandbookChunk.id))):
            print("The handbook is empty: run scripts/ingest_handbook.py first.", file=sys.stderr)
            return 2
        today = datetime.now(get_settings().tz).date()
        results = run_cases(
            session,
            budgeted,
            cases,
            today=today,
            retries=args.retries,
            on_result=lambda result: print(format_result(result), flush=True),
        )
    print(format_summary(results, len(cases), budgeted.calls))
    return 0 if len(results) == len(cases) and all(result.passed for result in results) else 1


def needs_handbook(cases: Sequence[EvalCase]) -> bool:
    return any("search_policy" in case.expected_tools for case in cases)


if __name__ == "__main__":
    sys.exit(main())
