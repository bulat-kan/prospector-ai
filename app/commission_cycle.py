from dataclasses import dataclass
from datetime import date


COMMISSION_CYCLE_START_DAY = 29
COMMISSION_CYCLE_END_DAY = 28


@dataclass(frozen=True)
class CommissionCycle:
    cycle_start: date
    cycle_end: date


def previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def get_commission_cycle(value: date) -> CommissionCycle:
    """Return the 29th-through-28th commission cycle containing a date."""
    if value.day >= COMMISSION_CYCLE_START_DAY:
        end_year, end_month = next_month(value.year, value.month)
        return CommissionCycle(
            cycle_start=date(value.year, value.month, COMMISSION_CYCLE_START_DAY),
            cycle_end=date(end_year, end_month, COMMISSION_CYCLE_END_DAY),
        )

    start_year, start_month = previous_month(value.year, value.month)
    return CommissionCycle(
        cycle_start=date(start_year, start_month, COMMISSION_CYCLE_START_DAY),
        cycle_end=date(value.year, value.month, COMMISSION_CYCLE_END_DAY),
    )


def format_commission_cycle(cycle: CommissionCycle) -> str:
    """Format a commission cycle for concise display."""
    start = cycle.cycle_start
    end = cycle.cycle_end
    start_text = f"{start:%b} {start.day}"
    if start.year != end.year:
        start_text = f"{start_text}, {start.year}"
    return f"{start_text} – {end:%b} {end.day}, {end.year}"
