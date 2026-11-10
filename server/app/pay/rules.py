"""Pay rules: the configuration `calculate` needs (product-definition §6.1).

v1 has daily overtime tiers only. Premiums (night, weekend) are meant to join `PayRules` as further
fields and be applied by `calculate` as additional lines, without touching the tier logic.
"""

from dataclasses import dataclass
from decimal import Decimal

SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class OvertimeTier:
    """A band of daily hours [from_hour, to_hour) paid at `multiplier` × the hourly rate.

    `to_hour=None` means open-ended. Bounds may be fractional but must fall on whole seconds.
    """

    from_hour: Decimal
    to_hour: Decimal | None
    multiplier: Decimal

    def __post_init__(self) -> None:
        if self.from_hour < 0:
            raise ValueError("from_hour must not be negative")
        if self.to_hour is not None and self.to_hour <= self.from_hour:
            raise ValueError("to_hour must be greater than from_hour")
        if self.multiplier <= 0:
            raise ValueError("multiplier must be positive")
        for bound in (self.from_hour, self.to_hour):
            if bound is not None and (bound * SECONDS_PER_HOUR) % 1 != 0:
                raise ValueError("tier bounds must be whole seconds")

    @property
    def from_second(self) -> int:
        return int(self.from_hour * SECONDS_PER_HOUR)

    @property
    def to_second(self) -> int | None:
        return None if self.to_hour is None else int(self.to_hour * SECONDS_PER_HOUR)


@dataclass(frozen=True)
class PayRules:
    """Tiers must start at 0, be contiguous, and end with exactly one open-ended tier."""

    tiers: tuple[OvertimeTier, ...]

    def __post_init__(self) -> None:
        if not self.tiers:
            raise ValueError("at least one tier is required")
        if self.tiers[0].from_hour != 0:
            raise ValueError("the first tier must start at hour 0")
        for tier, following in zip(self.tiers, self.tiers[1:], strict=False):
            if tier.to_hour is None:
                raise ValueError("only the last tier may be open-ended")
            if tier.to_hour != following.from_hour:
                raise ValueError("tiers must be contiguous")
        if self.tiers[-1].to_hour is not None:
            raise ValueError("the last tier must be open-ended")

    @classmethod
    def default(cls) -> "PayRules":
        """Hours 1–8 at 100 %, 9–10 at 125 %, 11+ at 150 % (product-definition §6.1)."""
        return cls(
            tiers=(
                OvertimeTier(Decimal("0"), Decimal("8"), Decimal("1.00")),
                OvertimeTier(Decimal("8"), Decimal("10"), Decimal("1.25")),
                OvertimeTier(Decimal("10"), None, Decimal("1.50")),
            )
        )
