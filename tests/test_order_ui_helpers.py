from datetime import date
from decimal import Decimal

from app.enums import SaleStatus
from app.order_service import OrderSummary
from app.order_ui_helpers import (
    CANCELED_ORDER_WARNING,
    LEGACY_INSTALLED_ORDER_WARNING,
    NONCOMMISSIONABLE_ORDER_WARNING,
    order_canceled_message,
    order_created_from_opportunity_message,
    order_created_message,
    order_display_record,
    order_products_label,
    order_updated_message,
    order_warning_for_status,
    sale_status_label,
    validate_order_item_rows,
)


def _summary() -> OrderSummary:
    return OrderSummary(
        order_id=99,
        order_date=date(2026, 7, 15),
        company_id=1,
        company_name="Sunshine Plumbing LLC",
        location_id=2,
        location_name="Spring Hill office",
        contact_id=3,
        contact_name="John Carter",
        opportunity_id=4,
        opportunity_name="Account Review",
        status=SaleStatus.SUBMITTED,
        status_display="Submitted",
        product_names=("Business Internet", "Business Mobile"),
        item_count=2,
        total_quantity=11,
        total_incremental_mrr=Decimal("900.00"),
        external_order_number="ABC-123",
    )


def test_order_status_labels_are_friendly() -> None:
    assert sale_status_label(SaleStatus.DRAFT) == "Draft"
    assert sale_status_label("CANCELED") == "Canceled"
    assert sale_status_label(SaleStatus.INSTALLED) == "Installed (Legacy)"


def test_order_display_record_hides_internal_ids() -> None:
    record = order_display_record(_summary())

    assert record["Company"] == "Sunshine Plumbing LLC"
    assert record["Products"] == "Business Internet, Business Mobile"
    assert record["Incremental MRR"] == "$900.00"
    assert "order_id" not in record
    assert "company_id" not in record


def test_order_warning_texts_are_status_specific() -> None:
    assert order_warning_for_status(SaleStatus.DRAFT) == NONCOMMISSIONABLE_ORDER_WARNING
    assert order_warning_for_status(SaleStatus.SUBMITTED) == NONCOMMISSIONABLE_ORDER_WARNING
    assert order_warning_for_status(SaleStatus.SCHEDULED) == NONCOMMISSIONABLE_ORDER_WARNING
    assert order_warning_for_status(SaleStatus.CANCELED) == CANCELED_ORDER_WARNING
    assert order_warning_for_status(SaleStatus.INSTALLED) == LEGACY_INSTALLED_ORDER_WARNING


def test_validate_order_item_rows_rejects_missing_duplicate_negative_and_zero_values() -> None:
    result = validate_order_item_rows(
        [
            {"product_code": None, "quantity": 1, "incremental_mrr": "0.00"},
            {"product_code": "BUSINESS_INTERNET", "quantity": 0, "incremental_mrr": "0.00"},
            {"product_code": "BUSINESS_INTERNET", "quantity": 1, "incremental_mrr": "-1.00"},
        ]
    )

    assert result.errors["product_0"] == "Select a product."
    assert result.errors["quantity_1"] == "Quantity must be greater than zero."
    assert result.errors["product_2"] == "This product is already included in the order."
    assert result.errors["mrr_2"] == "Incremental MRR cannot be negative."


def test_validate_order_item_rows_accepts_valid_rows_and_quantizes_money() -> None:
    result = validate_order_item_rows(
        [{"product_code": "BUSINESS_INTERNET", "quantity": 2, "incremental_mrr": "100.005", "notes": "Install"}]
    )

    assert result.errors == {}
    assert result.valid_rows[0]["incremental_mrr"] == Decimal("100.01")


def test_order_message_helpers() -> None:
    assert order_products_label(()) == "No products"
    assert "Sunshine Plumbing LLC" in order_created_message("Sunshine Plumbing LLC", 2, Decimal("900.00"))
    assert "Account Review" in order_created_from_opportunity_message("Account Review", "Sunshine Plumbing LLC")
    assert order_updated_message(12) == "Order 12 updated successfully."
    assert order_canceled_message(12) == "Order 12 canceled."
