"""Explain why a week could not be filled, and what the manager could relax.

    cd server && uv run python scripts/debug_schedule.py --week 2026-11-15
    cd server && uv run python scripts/debug_schedule.py --week 2026-11-15 --min-rest 6

Read-only: it runs the solver in trace mode on the development database through
`schedule_service.propose_schedule` and prints the unfilled slots with the reason each employee
could not take them, the options that would fill more (one rule at a time), and a trace summary.
Nothing is saved. The `debug-schedule` skill drives it.
"""

import argparse
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date
from pathlib import Path

# Running the file puts scripts/ on sys.path, not the server root that holds `app`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import scheduler  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.core.enums import Role  # noqa: E402
from app.core.errors import DomainError  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.scheduler import Constraint, SchedulingRules, TraceKind  # noqa: E402
from app.scheduler.explain import CONSTRAINT_PHRASES, describe_shift  # noqa: E402
from app.services import schedule_service  # noqa: E402
from app.services.schedule_service import Proposal  # noqa: E402


def build_report(
    session: Session, current_user: User, week_start: date, rules: SchedulingRules
) -> str:
    """The full text report for one week under `rules`. Raises DomainError for a bad week."""
    proposal = schedule_service.propose_schedule(
        session, current_user, week_start, rules=rules, trace=True
    )
    result = proposal.result
    total = sum(shift.required_staff for shift in proposal.shifts)
    finished = "search finished" if result.complete else "search budget used up"
    lines = [
        f"Week of {week_start}",
        f"Rules: minimum rest {rules.min_rest_hours:g} h, max {rules.max_shifts_per_week} shifts "
        f"per week, search budget {rules.max_steps} steps",
        f"Positions filled: {result.score.filled} of {total} ({finished}; {result.steps} steps)",
    ]
    if not result.unfilled:
        lines.append("Every position is filled.")
    else:
        lines += ["", "Unfilled slots", *unfilled_lines(proposal)]
        lines += [
            "",
            *what_if_lines(session, current_user, week_start, rules, result.score.filled, total),
        ]
    lines += ["", trace_line(result)]
    return "\n".join(lines)


def unfilled_lines(proposal: Proposal) -> list[str]:
    zone = get_settings().tz
    names = {employee.id: employee.name for employee in proposal.employees}
    shifts = {shift.id: shift for shift in proposal.shifts}
    lines: list[str] = []
    for slot, sentence in zip(proposal.result.unfilled, proposal.sentences, strict=True):
        lines.append(f"- {sentence}")
        blocked: dict[int, list[str]] = defaultdict(list)
        unanswered: list[str] = []
        for reason in slot.reasons:
            if reason.constraint is Constraint.availability:
                unanswered.append(names[reason.employee_id])
                continue
            detail = CONSTRAINT_PHRASES[reason.constraint]
            if reason.shift_id is not None:
                other = shifts[reason.shift_id]
                solver_shift = scheduler.Shift(
                    other.id, other.starts_at, other.ends_at, other.required_staff
                )
                detail += f" with {describe_shift(solver_shift, zone)}"
            blocked[reason.employee_id].append(detail)
        lines += [f"    {names[who]}: {', '.join(details)}" for who, details in blocked.items()]
        if unanswered:
            lines.append(f"    Did not answer available: {', '.join(unanswered)}")
    return lines


def what_if_lines(
    session: Session,
    current_user: User,
    week_start: date,
    rules: SchedulingRules,
    filled: int,
    total: int,
) -> list[str]:
    """Each rule relaxed on its own; these are options for the manager, not fixes."""
    options = []
    if rules.min_rest_hours > 0:
        options.append(("if there were no minimum rest", replace(rules, min_rest_hours=0)))
    more = rules.max_shifts_per_week + 1
    options.append(
        (f"if employees could work {more} shifts a week", replace(rules, max_shifts_per_week=more))
    )
    lines = ["What if (one change at a time, same availability; options, not fixes)"]
    for label, relaxed in options:
        alternative = schedule_service.propose_schedule(
            session, current_user, week_start, rules=relaxed
        ).result.score.filled
        delta = alternative - filled
        outcome = f"fills {alternative} of {total} ({delta:+d})" if delta else "no change"
        lines.append(f"- {label}: {outcome}")
    lines.append(
        "- Asking the employees listed under 'Did not answer available' is the other lever."
    )
    return lines


def trace_line(result: scheduler.ScheduleResult) -> str:
    kinds = Counter(event.kind for event in result.trace)
    eliminated = Counter(
        event.constraint for event in result.trace if event.kind is TraceKind.exclude
    )
    by_constraint = ", ".join(f"{c.value} {n}" for c, n in sorted(eliminated.items()))
    line = (
        f"Trace: {kinds[TraceKind.assign]} placements, {kinds[TraceKind.backtrack]} backtracks, "
        f"{sum(eliminated.values())} candidates eliminated ({by_constraint or 'none'})"
    )
    return line + (" - trace truncated" if result.trace_truncated else "")


def find_manager(session: Session, email: str | None) -> User:
    query = (
        select(User).where(User.email == email)
        if email
        else select(User).where(User.role == Role.manager, User.is_active).order_by(User.id)
    )
    user = session.scalar(query.limit(1))
    if user is None:
        raise SystemExit(
            f"No user found{f' with email {email}' if email else ' with role manager'}."
        )
    return user


def main() -> None:
    parser = argparse.ArgumentParser(description="Explain why a week could not be filled.")
    parser.add_argument(
        "--week", required=True, type=date.fromisoformat, help="the Sunday, YYYY-MM-DD"
    )
    parser.add_argument(
        "--min-rest", type=float, help="minimum rest in hours (default: configured)"
    )
    parser.add_argument("--max-shifts", type=int, help="max shifts per week (default: configured)")
    parser.add_argument("--max-steps", type=int, help="search budget (default: configured)")
    parser.add_argument("--as", dest="email", help="act as this manager (default: the first one)")
    args = parser.parse_args()

    rules = get_settings().scheduling_rules
    overrides = {
        "min_rest_hours": args.min_rest,
        "max_shifts_per_week": args.max_shifts,
        "max_steps": args.max_steps,
    }
    rules = replace(rules, **{key: value for key, value in overrides.items() if value is not None})
    with SessionLocal() as session:
        try:
            print(build_report(session, find_manager(session, args.email), args.week, rules))
        except DomainError as error:
            raise SystemExit(f"{error.code}: {error.message}") from error


if __name__ == "__main__":
    main()
