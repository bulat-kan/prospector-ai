from decimal import Decimal

from app.enums import ContactRole
from app.ui_helpers import (
    calculate_progress,
    clamp_progress,
    format_currency,
    format_percentage,
    format_phone,
    friendly_label,
    month_label,
    normalize_website_url,
    tier_label,
)


def test_currency_formatting() -> None:
    assert format_currency(Decimal("2200.25")) == "$2,200.25"


def test_percentage_formatting() -> None:
    assert format_percentage(Decimal("7.50")) == "7.5%"


def test_progress_below_range_clamps_to_zero() -> None:
    assert clamp_progress(-0.5) == 0.0


def test_progress_above_range_clamps_to_one() -> None:
    assert clamp_progress(1.5) == 1.0


def test_current_tier_progress_calculation() -> None:
    assert calculate_progress(5, 5, 10) == 0.0
    assert calculate_progress(7, 5, 10) == 0.4


def test_highest_tier_behavior() -> None:
    assert calculate_progress(30, 30, None) == 1.0


def test_month_label_formatting() -> None:
    assert month_label(2026, 7) == "July 2026"


def test_decimal_values_format_correctly() -> None:
    assert format_currency(Decimal("1350")) == "$1,350.00"


def test_tier_label_uses_en_dash() -> None:
    assert tier_label("5-9") == "5–9"


def test_friendly_label_formats_enums_and_lead_source() -> None:
    assert friendly_label(ContactRole.DECISION_MAKER) == "Decision Maker"
    assert friendly_label("AE_FOUND") == "AE Found"


def test_phone_and_website_display_helpers() -> None:
    assert format_phone("7275550100") == "(727) 555-0100"
    assert normalize_website_url("example.com") == "https://example.com"
