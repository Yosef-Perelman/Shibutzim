"""Pure checks of one assistant run against its case. Each returns the reasons it failed."""

import re
from datetime import date
from typing import Any

from app.assistant.agent import AgentReply
from app.core.time import weekday_sunday_based
from app.scheduler.explain import WEEKDAY_NAMES
from evals.types import EvalCase, Fact

ToolResults = dict[str, list[dict[str, Any]]]  # tool name -> the results of its calls, in order
NUMBER = re.compile(r"\d+(\.\d+)?")
ZERO_WORDS = (
    "zero",
    "nothing",
    "none",
    "no pay",
    "no hours",
    "no earnings",
    "no time entries",
    "did not work",
    "didn't work",
)


def check_case(case: EvalCase, reply: AgentReply, results: ToolResults) -> list[str]:
    """Every way `reply` falls short of `case`; an empty list means the case passed."""
    if not reply.text.strip():
        return ["the answer is empty"]
    return [
        *check_tools(case, reply),
        *[failure for fact in case.facts for failure in check_fact(fact, reply.text, results)],
        *check_citations(case, reply),
        *check_text(case, reply.text),
        *check_proposal(case, reply),
    ]


def check_tools(case: EvalCase, reply: AgentReply) -> list[str]:
    called = [call.name for call in reply.tool_calls]
    failures = [f"expected a call to {tool}" for tool in case.expected_tools if tool not in called]
    failures += [f"must not call {tool}" for tool in case.forbidden_tools if tool in called]
    if case.max_tool_calls is not None and len(called) > case.max_tool_calls:
        failures.append(f"made {len(called)} tool calls, at most {case.max_tool_calls} allowed")
    return failures


def check_fact(fact: Fact, text: str, results: ToolResults) -> list[str]:
    found = results.get(fact.tool, [])
    if not found:
        return [f"no result from {fact.tool} to check against"]
    failures = []
    for result in found if fact.every else found[:1]:
        value = resolve_path(result, fact.path)
        if value is None:
            if not fact.optional:
                failures.append(f"{fact.tool} has no value at {fact.path}")
        elif not appears(str(value), text):
            failures.append(f"the answer does not say {fact.tool}.{fact.path} = {value}")
    return failures


def check_citations(case: EvalCase, reply: AgentReply) -> list[str]:
    failures = []
    if case.citation and case.citation not in reply.citations:
        failures.append(f"expected a citation of the {case.citation} section")
    if case.no_citation and reply.citations:
        failures.append(f"must not cite a section, but cited {', '.join(reply.citations)}")
    return failures


def check_text(case: EvalCase, text: str) -> list[str]:
    haystack = normalize(text)
    failures = [
        f"the answer does not contain '{needle}'"
        for needle in case.must_contain
        if normalize(needle) not in haystack
    ]
    if case.must_contain_any and not any(normalize(n) in haystack for n in case.must_contain_any):
        failures.append(f"the answer contains none of: {', '.join(case.must_contain_any)}")
    failures += [
        f"the answer mentions '{needle}'"
        for needle in case.must_not_contain
        if normalize(needle) in haystack
    ]
    return failures


def check_proposal(case: EvalCase, reply: AgentReply) -> list[str]:
    proposal = reply.proposal
    if not case.expects_proposal:
        return ["did not expect a schedule proposal"] if proposal else []
    if proposal is None:
        return ["expected a schedule proposal"]
    if case.proposal_days_off is None:
        return []
    actual = sorted((item["name"], weekday_of(item["day"])) for item in proposal["unavailable"])
    expected = sorted(case.proposal_days_off)
    if actual != expected:
        return [f"days off in the proposal are {actual}, expected {expected}"]
    return []


def weekday_of(day: str) -> str:
    return WEEKDAY_NAMES[weekday_sunday_based(date.fromisoformat(day))]


def resolve_path(result: Any, path: str) -> Any:
    """The value at a dotted path through dicts and lists, or None if there is none."""
    current = result
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
        if current is None:
            return None
    return current


def normalize(text: str) -> str:
    """Lower case without thousands separators, so "3,198.13" and "3198.13" compare equal."""
    return text.replace(",", "").casefold()


def appears(value: str, text: str) -> bool:
    """Does the answer state `value`? Numbers match however the zeros are written (8.00, 8.0, 8)."""
    haystack = normalize(text)
    if not NUMBER.fullmatch(value):
        return normalize(value) in haystack
    number = value.rstrip("0").rstrip(".") if "." in value else value
    body = re.escape(number)
    tail = r"0*" if "." in number else r"(?:\.0+)?"
    if re.search(rf"(?<![\d.]){body}{tail}(?!\d|\.\d)", haystack):
        return True
    # Zero is also said in words: "you earned nothing", "no hours".
    return float(value) == 0 and any(word in haystack for word in ZERO_WORDS)
