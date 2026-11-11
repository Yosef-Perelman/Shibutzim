"""What an eval case expects. A case is data; `checks.py` compares a run with it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    """A value from a tool result that the answer must repeat, so it is never made up.

    `path` walks the result with dots, e.g. `total_amount` or `shifts.0.start`. By default the
    first result of the tool is checked; `every` checks all of them. `optional` skips the fact when
    the path does not exist (a week without shifts has no first shift).
    """

    tool: str
    path: str
    every: bool = False
    optional: bool = False


@dataclass(frozen=True)
class EvalCase:
    id: str
    persona: str  # the seeded user who asks, by name
    question: str
    expected_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    max_tool_calls: int | None = None
    facts: tuple[Fact, ...] = ()
    citation: str | None = None  # a handbook section title the answer must name
    no_citation: bool = False  # the answer must not name any section
    must_contain: tuple[str, ...] = ()
    must_contain_any: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()
    expects_proposal: bool = False
    proposal_days_off: tuple[tuple[str, str], ...] | None = None  # (employee name, weekday)
