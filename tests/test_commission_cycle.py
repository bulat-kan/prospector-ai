from datetime import date

from app.commission_cycle import CommissionCycle, format_commission_cycle, get_commission_cycle


def assert_cycle(value: date, expected_start: date, expected_end: date) -> None:
    cycle = get_commission_cycle(value)
    assert cycle.cycle_start == expected_start
    assert cycle.cycle_end == expected_end


def test_commission_cycle_before_start_day() -> None:
    assert_cycle(date(2026, 7, 15), date(2026, 6, 29), date(2026, 7, 28))


def test_commission_cycle_on_28th() -> None:
    assert_cycle(date(2026, 7, 28), date(2026, 6, 29), date(2026, 7, 28))


def test_commission_cycle_on_29th() -> None:
    assert_cycle(date(2026, 7, 29), date(2026, 7, 29), date(2026, 8, 28))


def test_commission_cycle_on_30th() -> None:
    assert_cycle(date(2026, 7, 30), date(2026, 7, 29), date(2026, 8, 28))


def test_commission_cycle_on_31st() -> None:
    assert_cycle(date(2026, 7, 31), date(2026, 7, 29), date(2026, 8, 28))


def test_commission_cycle_january_date() -> None:
    assert_cycle(date(2027, 1, 5), date(2026, 12, 29), date(2027, 1, 28))


def test_commission_cycle_february_date() -> None:
    assert_cycle(date(2026, 2, 14), date(2026, 1, 29), date(2026, 2, 28))


def test_commission_cycle_leap_year() -> None:
    assert_cycle(date(2028, 2, 29), date(2028, 2, 29), date(2028, 3, 28))


def test_commission_cycle_year_transition_after_start_day() -> None:
    assert_cycle(date(2026, 12, 30), date(2026, 12, 29), date(2027, 1, 28))


def test_format_commission_cycle_same_year() -> None:
    cycle = CommissionCycle(date(2026, 6, 29), date(2026, 7, 28))

    assert format_commission_cycle(cycle) == "Jun 29 – Jul 28, 2026"


def test_format_commission_cycle_year_transition() -> None:
    cycle = CommissionCycle(date(2026, 12, 29), date(2027, 1, 28))

    assert format_commission_cycle(cycle) == "Dec 29, 2026 – Jan 28, 2027"
