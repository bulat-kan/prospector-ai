from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.enums import SaleStatus
from app.order_service import OrderSummary, money, normalize_order_status, order_status_display
from app.ui_helpers import format_currency


ORDER_ENTRY_STATUSES = (
    SaleStatus.DRAFT,
    SaleStatus.SUBMITTED,
    SaleStatus.SCHEDULED,
    SaleStatus.CANCELED,
)
ORDER_BROWSE_STATUSES = (
    SaleStatus.DRAFT,
    SaleStatus.SUBMITTED,
    SaleStatus.SCHEDULED,
    SaleStatus.PARTIALLY_FULFILLED,
    SaleStatus.FULFILLED,
    SaleStatus.CANCELED,
    SaleStatus.INSTALLED,
    SaleStatus.DISCONNECTED,
)
NONCOMMISSIONABLE_ORDER_WARNING = (
    "This order does not count toward commission until qualifying fixed services are installed "
    "or mobile lines are activated."
)
CANCELED_ORDER_WARNING = "Canceled orders are retained for history and do not count toward commission."
LEGACY_INSTALLED_ORDER_WARNING = "Legacy Installed orders remain read-only except for notes."


@dataclass(frozen=True)
class OrderItemRowValidationResult:
    errors: dict[str, str]
    valid_rows: tuple[dict[str, object], ...]


def sale_status_label(status: SaleStatus | str) -> str:
    return order_status_display(status)


def order_products_label(product_names: tuple[str, ...]) -> str:
    return ", ".join(product_names) if product_names else "No products"


def parse_money_input(value: object, field_name: str) -> tuple[Optional[Decimal], Optional[str]]:
    if value in (None, ""):
        return Decimal("0.00"), None
    try:
        amount = money(value)  # type: ignore[arg-type]
    except (InvalidOperation, ValueError):
        return None, f"{field_name} must be a valid dollar amount."
    if amount < Decimal("0.00"):
        return None, f"{field_name} cannot be negative."
    return amount, None


def validate_order_item_rows(rows: list[dict[str, object]]) -> OrderItemRowValidationResult:
    errors: dict[str, str] = {}
    valid_rows: list[dict[str, object]] = []
    selected_codes: set[str] = set()
    for index, row in enumerate(rows):
        product_code = str(row.get("product_code") or "")
        if not product_code:
            errors[f"product_{index}"] = "Select a product."
            continue
        if product_code in selected_codes:
            errors[f"product_{index}"] = "This product is already included in the order."
        selected_codes.add(product_code)

        quantity = int(row.get("quantity") or 0)
        if quantity <= 0:
            errors[f"quantity_{index}"] = "Quantity must be greater than zero."

        mrr, mrr_error = parse_money_input(row.get("incremental_mrr"), "Incremental MRR")
        if mrr_error:
            errors[f"mrr_{index}"] = mrr_error

        if not any(key.endswith(f"_{index}") for key in errors):
            valid_rows.append(
                {
                    **row,
                    "product_code": product_code,
                    "quantity": quantity,
                    "incremental_mrr": mrr or Decimal("0.00"),
                }
            )

    if not valid_rows:
        errors["products"] = "Select at least one product."
    return OrderItemRowValidationResult(errors=errors, valid_rows=tuple(valid_rows))


def order_display_record(summary: OrderSummary) -> dict[str, object]:
    return {
        "Order date": summary.order_date.isoformat(),
        "Company": summary.company_name,
        "Location": summary.location_name or "Unassigned",
        "Contact": summary.contact_name or "Unassigned",
        "Source opportunity": summary.opportunity_name or "",
        "Status": summary.status_display,
        "Products": order_products_label(summary.product_names),
        "Item count": summary.item_count,
        "Total quantity": summary.total_quantity,
        "Incremental MRR": format_currency(summary.total_incremental_mrr),
        "External order number": summary.external_order_number or "",
    }


def order_warning_for_status(status: SaleStatus | str) -> Optional[str]:
    normalized = normalize_order_status(status)
    if normalized == SaleStatus.CANCELED:
        return CANCELED_ORDER_WARNING
    if normalized == SaleStatus.INSTALLED:
        return LEGACY_INSTALLED_ORDER_WARNING
    if normalized in {SaleStatus.DRAFT, SaleStatus.SUBMITTED, SaleStatus.SCHEDULED}:
        return NONCOMMISSIONABLE_ORDER_WARNING
    return None


def order_created_message(company_name: object, item_count: int, total_mrr: Decimal) -> str:
    company = str(company_name).strip() if company_name else "the selected company"
    return f'Order created successfully for {company} with {item_count} item{"s" if item_count != 1 else ""} and {format_currency(total_mrr)} MRR.'


def order_created_from_opportunity_message(opportunity_name: object, company_name: object) -> str:
    opportunity = str(opportunity_name).strip() if opportunity_name else "the selected opportunity"
    company = str(company_name).strip() if company_name else "the selected company"
    return f'Order created from "{opportunity}" for {company}.'


def order_updated_message(order_id: int) -> str:
    return f"Order {order_id} updated successfully."


def order_canceled_message(order_id: int) -> str:
    return f"Order {order_id} canceled."
