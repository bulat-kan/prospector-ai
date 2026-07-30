from decimal import Decimal
from enum import Enum
from typing import Optional

from app.validation import LEAD_SOURCE_LABELS, format_phone_display


MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def format_currency(value: Optional[Decimal]) -> str:
    if value is None:
        return "$0.00"
    return f"${value:,.2f}"


def format_percentage(value: Optional[Decimal]) -> str:
    if value is None:
        return "0%"
    normalized = value.normalize()
    return f"{normalized:f}%"


def clamp_progress(value: float) -> float:
    return max(0.0, min(1.0, value))


def calculate_progress(current: int, start: int, target: Optional[int]) -> float:
    if target is None or target <= start:
        return 1.0
    return clamp_progress((current - start) / (target - start))


def month_label(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month]} {year}"


def tier_label(value: Optional[str]) -> str:
    if not value:
        return "Below threshold"
    return value.replace("-", "–")


def friendly_label(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        value = value.value
    text = str(value)
    if text in LEAD_SOURCE_LABELS:
        return LEAD_SOURCE_LABELS[text]
    return text.replace("_", " ").title()


def format_phone(value: Optional[str]) -> str:
    return format_phone_display(value)


def normalize_website_url(value: Optional[str]) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if stripped.startswith(("http://", "https://")):
        return stripped
    return f"https://{stripped}"
