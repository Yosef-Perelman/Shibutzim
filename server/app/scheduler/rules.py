"""Scheduling configuration (product-definition §6.2). Plain data, validated on creation."""

from dataclasses import dataclass
from datetime import timedelta

DEFAULT_MIN_REST_HOURS = 8
DEFAULT_MAX_SHIFTS_PER_WEEK = 5
DEFAULT_MAX_STEPS = 200_000


@dataclass(frozen=True)
class SchedulingRules:
    """Everything the solver needs besides the problem itself.

    `max_steps` is the search budget: a count of search nodes, not seconds, so a solve is
    reproducible and the module never reads the clock (coding-rules).
    """

    min_rest_hours: float = DEFAULT_MIN_REST_HOURS
    max_shifts_per_week: int = DEFAULT_MAX_SHIFTS_PER_WEEK
    max_steps: int = DEFAULT_MAX_STEPS

    def __post_init__(self) -> None:
        if self.min_rest_hours < 0:
            raise ValueError("min_rest_hours must not be negative")
        if self.max_shifts_per_week < 1:
            raise ValueError("max_shifts_per_week must be at least 1")
        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1")

    @property
    def min_rest(self) -> timedelta:
        return timedelta(hours=self.min_rest_hours)

    @classmethod
    def default(cls) -> "SchedulingRules":
        return cls()
