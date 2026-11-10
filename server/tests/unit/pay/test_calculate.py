"""The pay matrix (testing-rules, product-definition §5.4 and §6.1).

Expected values are computed by hand in the comments. Default tiers: hours 1–8 at 100 %, 9–10 at
125 %, 11+ at 150 %, applied per work day after summing that day's entries. Amounts are rounded per
tier line (ROUND_HALF_UP) and every total is the sum of its lines (plan 001, open question 7). Hours
are never rounded.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.pay import Entry, OvertimeTier, PayBreakdown, PayRules, calculate

TZ = ZoneInfo("Asia/Jerusalem")
RATE = Decimal("50.00")
RULES = PayRules.default()
MON = date(2026, 3, 9)
TUE = date(2026, 3, 10)
D = Decimal

DayLines = list[tuple[Decimal, Decimal, Decimal]]
ExpectedDays = list[tuple[date, DayLines, Decimal]]


def at(day: date, hhmm: str) -> datetime:
    hour, minute = (int(part) for part in hhmm.split(":"))
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


def entry(day: date, start: str, end: str) -> Entry:
    """An entry on `day` in local time; an end at or before the start means it ends the next day."""
    clock_in = at(day, start)
    clock_out = at(day, end)
    if clock_out <= clock_in:
        clock_out += timedelta(days=1)
    return Entry(clock_in=clock_in, clock_out=clock_out)


def lines_of(breakdown: PayBreakdown) -> ExpectedDays:
    """(work_day, [(multiplier, hours, amount), ...], day amount) per day, as plain literals."""
    return [
        (
            day.work_day,
            [(line.tier.multiplier, line.hours, line.amount) for line in day.lines],
            day.amount,
        )
        for day in breakdown.days
    ]


# --- The mandatory matrix, which is also the edge-case matrix of the "overtime_tiers" rule ---


@pytest.mark.pay_rule("overtime_tiers")
@pytest.mark.parametrize(
    ("entries", "expected_days", "expected_hours", "expected_amount"),
    [
        pytest.param(
            [entry(MON, "08:00", "16:00")],
            # 8h, all in tier 1: 8 × 50.00 = 400.00
            [(MON, [(D("1.00"), D("8"), D("400.00"))], D("400.00"))],
            D("8"),
            D("400.00"),
            id="exactly_8h",
        ),
        pytest.param(
            [entry(MON, "08:00", "17:00")],
            # 9h: 8 × 50 = 400.00; 1 × 50 × 1.25 = 62.50; total 462.50
            [
                (
                    MON,
                    [(D("1.00"), D("8"), D("400.00")), (D("1.25"), D("1"), D("62.50"))],
                    D("462.50"),
                )
            ],
            D("9"),
            D("462.50"),
            id="9h",
        ),
        pytest.param(
            [entry(MON, "08:00", "20:00")],
            # 12h: 400.00 + 2 × 62.50 = 125.00 + 2 × 75.00 = 150.00; total 675.00
            [
                (
                    MON,
                    [
                        (D("1.00"), D("8"), D("400.00")),
                        (D("1.25"), D("2"), D("125.00")),
                        (D("1.50"), D("2"), D("150.00")),
                    ],
                    D("675.00"),
                )
            ],
            D("12"),
            D("675.00"),
            id="with_overtime_tiers",
        ),
        pytest.param(
            [entry(MON, "07:00", "11:00"), entry(MON, "16:00", "22:00")],
            # split shift 4h + 6h = 10h, summed before tiers: 400.00 + 2 × 62.50; total 525.00
            [
                (
                    MON,
                    [(D("1.00"), D("8"), D("400.00")), (D("1.25"), D("2"), D("125.00"))],
                    D("525.00"),
                )
            ],
            D("10"),
            D("525.00"),
            id="split_shift",
        ),
        pytest.param(
            [entry(MON, "22:00", "06:00")],
            # 22:00–06:00 = 8h on one work day (Monday, when it started), not split: 400.00
            [(MON, [(D("1.00"), D("8"), D("400.00"))], D("400.00"))],
            D("8"),
            D("400.00"),
            id="crossing_midnight",
        ),
        pytest.param(
            [entry(MON, "08:00", "16:00"), entry(TUE, "08:00", "17:00")],
            # Monday 8h = 400.00; Tuesday 9h = 462.50; total 862.50 over 17h
            [
                (MON, [(D("1.00"), D("8"), D("400.00"))], D("400.00")),
                (
                    TUE,
                    [(D("1.00"), D("8"), D("400.00")), (D("1.25"), D("1"), D("62.50"))],
                    D("462.50"),
                ),
            ],
            D("17"),
            D("862.50"),
            id="two_work_days",
        ),
        pytest.param([], [], D("0"), D("0.00"), id="zero_hours"),
        pytest.param(
            [entry(MON, "08:00", "16:00"), entry(MON, "16:00", "16:01")],
            # 8h01m: 400.00 + 60 s × 50 × 1.25 / 3600 = 1.041666… = 1.04; total 401.04
            [
                (
                    MON,
                    [(D("1.00"), D("8"), D("400.00")), (D("1.25"), D(60) / D(3600), D("1.04"))],
                    D("401.04"),
                )
            ],
            D(28_860) / D(3600),
            D("401.04"),
            id="at_boundary",
        ),
    ],
)
def test_calculate_matrix(
    entries: list[Entry],
    expected_days: ExpectedDays,
    expected_hours: Decimal,
    expected_amount: Decimal,
) -> None:
    breakdown = calculate(entries, RATE, RULES, TZ)

    assert lines_of(breakdown) == expected_days
    assert breakdown.hours == expected_hours
    assert breakdown.amount == expected_amount


def test_calculate_exactly_8h_has_a_single_tier_line() -> None:
    breakdown = calculate([entry(MON, "08:00", "16:00")], RATE, RULES, TZ)

    assert len(breakdown.days) == 1
    assert len(breakdown.days[0].lines) == 1
    assert breakdown.days[0].seconds == 8 * 3600


def test_calculate_8h01m_opens_the_second_tier_for_sixty_seconds() -> None:
    breakdown = calculate([entry(MON, "08:00", "16:01")], RATE, RULES, TZ)

    second_line = breakdown.days[0].lines[1]
    assert second_line.seconds == 60
    assert second_line.tier.multiplier == D("1.25")


# --- Rounding ---


def test_calculate_rounds_half_up_to_the_cent() -> None:
    # 30 min × 10.01 = 5.005, which is 5.01 with ROUND_HALF_UP (bankers' rounding would give 5.00)
    breakdown = calculate([entry(MON, "08:00", "08:30")], D("10.01"), RULES, TZ)

    assert breakdown.amount == D("5.01")
    assert breakdown.hours == D("0.5")


def test_calculate_rounds_each_tier_line_and_sums_the_lines() -> None:
    # Custom tiers: first half hour at 100 %, the rest at 125 %. One hour at 10.01:
    #   line 1: 0.5 × 10.01 = 5.005 → 5.01;  line 2: 0.5 × 10.01 × 1.25 = 6.25625 → 6.26
    #   total 11.27
    # Rounding the unrounded sum (11.26125) would give 11.26 instead; the breakdown must add up.
    rules = PayRules(
        tiers=(
            OvertimeTier(D("0"), D("0.5"), D("1.00")),
            OvertimeTier(D("0.5"), None, D("1.25")),
        )
    )

    breakdown = calculate([entry(MON, "08:00", "09:00")], D("10.01"), rules, TZ)

    assert [line.amount for line in breakdown.days[0].lines] == [D("5.01"), D("6.26")]
    assert breakdown.days[0].amount == D("11.27")
    assert breakdown.amount == D("11.27")


def test_calculate_amounts_are_decimals_with_two_places() -> None:
    breakdown = calculate([entry(MON, "08:00", "17:00")], RATE, RULES, TZ)

    assert isinstance(breakdown.amount, Decimal)
    assert breakdown.amount.as_tuple().exponent == -2
    assert all(line.amount.as_tuple().exponent == -2 for line in breakdown.days[0].lines)


# --- Ordering, rules and validation ---


def test_calculate_accepts_entries_in_any_order_and_sorts_days() -> None:
    first = entry(MON, "07:00", "11:00")
    second = entry(MON, "16:00", "22:00")
    third = entry(TUE, "08:00", "16:00")

    ordered = calculate([first, second, third], RATE, RULES, TZ)
    shuffled = calculate([third, second, first], RATE, RULES, TZ)

    assert shuffled == ordered
    assert [day.work_day for day in shuffled.days] == [MON, TUE]


def test_calculate_uses_elapsed_time_across_a_dst_change() -> None:
    # 2026-03-26 22:00 to 03-27 06:00 local is 7 real hours (clocks skipped 02:00–03:00): 350.00
    breakdown = calculate([entry(date(2026, 3, 26), "22:00", "06:00")], RATE, RULES, TZ)

    assert breakdown.hours == D("7")
    assert breakdown.amount == D("350.00")


def test_calculate_with_custom_tiers() -> None:
    # 6h at 100 % then double time: 7h = 6 × 50 + 1 × 100 = 400.00
    rules = PayRules(
        tiers=(OvertimeTier(D("0"), D("6"), D("1.00")), OvertimeTier(D("6"), None, D("2.00")))
    )

    breakdown = calculate([entry(MON, "08:00", "15:00")], RATE, rules, TZ)

    assert lines_of(breakdown) == [
        (MON, [(D("1.00"), D("6"), D("300.00")), (D("2.00"), D("1"), D("100.00"))], D("400.00"))
    ]


def test_default_rules_match_the_product_definition() -> None:
    assert RULES.tiers == (
        OvertimeTier(D("0"), D("8"), D("1.00")),
        OvertimeTier(D("8"), D("10"), D("1.25")),
        OvertimeTier(D("10"), None, D("1.50")),
    )


@pytest.mark.parametrize(
    "tiers",
    [
        (),
        (OvertimeTier(D("1"), None, D("1.00")),),
        (OvertimeTier(D("0"), D("8"), D("1.00")), OvertimeTier(D("9"), None, D("1.25"))),
        (OvertimeTier(D("0"), D("8"), D("1.00")),),
        (OvertimeTier(D("0"), None, D("1.00")), OvertimeTier(D("8"), None, D("1.25"))),
    ],
    ids=["empty", "not_from_zero", "gap", "not_open_ended", "open_tier_not_last"],
)
def test_pay_rules_reject_non_contiguous_tiers(tiers: tuple[OvertimeTier, ...]) -> None:
    with pytest.raises(ValueError):
        PayRules(tiers=tiers)


def test_calculate_rejects_clock_out_before_clock_in() -> None:
    bad = Entry(clock_in=at(MON, "16:00"), clock_out=at(MON, "08:00"))

    with pytest.raises(ValueError, match="clock_out"):
        calculate([bad], RATE, RULES, TZ)


def test_calculate_rejects_naive_datetimes() -> None:
    bad = Entry(clock_in=datetime(2026, 3, 9, 8, 0), clock_out=datetime(2026, 3, 9, 16, 0))  # noqa: DTZ001

    with pytest.raises(ValueError, match="aware"):
        calculate([bad], RATE, RULES, TZ)


def test_calculate_rejects_negative_hourly_rate() -> None:
    with pytest.raises(ValueError, match="hourly_rate"):
        calculate([entry(MON, "08:00", "16:00")], D("-1"), RULES, TZ)
