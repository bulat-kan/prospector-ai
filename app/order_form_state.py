from copy import deepcopy
from datetime import date
from typing import Any, MutableMapping, Optional

from app.enums import SaleStatus
from app.form_state import set_flash_message


ORDER_ADD_RESET_PENDING_KEY = "order_add_reset_pending"
ORDER_CONVERT_RESET_PENDING_KEY = "order_convert_reset_pending"
ORDER_PENDING_PAGE_MODE_KEY = "order_pending_page_mode"
ORDER_ITEM_ROW_WIDGET_PREFIX = "order_item_row"
CONVERT_ORDER_ITEM_ROW_WIDGET_PREFIX = "convert_order_item_row"

ORDER_PAGE_BROWSE = "Browse orders"
ORDER_PAGE_ADD = "Add order"
ORDER_PAGE_CONVERT = "Convert opportunity"
ORDER_PAGE_DETAIL = "Order detail"
ORDER_PAGE_MODES = (
    ORDER_PAGE_BROWSE,
    ORDER_PAGE_ADD,
    ORDER_PAGE_CONVERT,
    ORDER_PAGE_DETAIL,
)

DEFAULT_ORDER_ITEM_ROW: dict[str, Any] = {
    "product_code": None,
    "quantity": 1,
    "incremental_mrr": "0.00",
    "notes": "",
    "source_opportunity_product_id": None,
}

ADD_ORDER_FORM_DEFAULTS: dict[str, Any] = {
    "order_company_id": None,
    "order_location_id": None,
    "order_contact_id": None,
    "order_opportunity_id": None,
    "order_date": None,
    "order_status": SaleStatus.DRAFT.value,
    "order_external_order_number": "",
    "order_customer_account_reference": "",
    "order_submitted_at": None,
    "order_notes": "",
    "order_item_rows": [deepcopy(DEFAULT_ORDER_ITEM_ROW)],
    "order_errors": {},
}

CONVERT_ORDER_FORM_DEFAULTS: dict[str, Any] = {
    "convert_opportunity_id": None,
    "convert_loaded_opportunity_id": None,
    "convert_location_id": None,
    "convert_contact_id": None,
    "convert_order_date": None,
    "convert_status": SaleStatus.DRAFT.value,
    "convert_external_order_number": "",
    "convert_customer_account_reference": "",
    "convert_submitted_at": None,
    "convert_notes": "",
    "convert_item_rows": [deepcopy(DEFAULT_ORDER_ITEM_ROW)],
    "convert_errors": {},
}

ORDER_PAGE_STATE_DEFAULTS: dict[str, Any] = {
    "selected_order_id": None,
    "order_page_mode": ORDER_PAGE_BROWSE,
}

ORDER_STATE_DEFAULTS: dict[str, Any] = {
    **ADD_ORDER_FORM_DEFAULTS,
    **CONVERT_ORDER_FORM_DEFAULTS,
    **ORDER_PAGE_STATE_DEFAULTS,
}


def initialize_order_form_state(state: MutableMapping[str, Any]) -> None:
    for key, value in ORDER_STATE_DEFAULTS.items():
        state.setdefault(key, deepcopy(value))


def _clear_widget_keys(state: MutableMapping[str, Any], prefix: str) -> None:
    for key in tuple(state):
        if str(key).startswith(f"{prefix}_"):
            del state[key]
    state.pop(f"{prefix}_add", None)


def reset_add_order_form_state(state: MutableMapping[str, Any]) -> None:
    for key, value in ADD_ORDER_FORM_DEFAULTS.items():
        state[key] = deepcopy(value)
    _clear_widget_keys(state, ORDER_ITEM_ROW_WIDGET_PREFIX)


def reset_convert_order_form_state(state: MutableMapping[str, Any]) -> None:
    for key, value in CONVERT_ORDER_FORM_DEFAULTS.items():
        state[key] = deepcopy(value)
    _clear_widget_keys(state, CONVERT_ORDER_ITEM_ROW_WIDGET_PREFIX)


def mark_order_form_reset_pending(
    state: MutableMapping[str, Any],
    *,
    add: bool = False,
    convert: bool = False,
    page_mode: str = ORDER_PAGE_DETAIL,
) -> None:
    if add:
        state[ORDER_ADD_RESET_PENDING_KEY] = True
    if convert:
        state[ORDER_CONVERT_RESET_PENDING_KEY] = True
    state[ORDER_PENDING_PAGE_MODE_KEY] = page_mode


def apply_pending_order_form_reset(state: MutableMapping[str, Any]) -> bool:
    initialize_order_form_state(state)
    changed = False
    if state.get(ORDER_ADD_RESET_PENDING_KEY):
        reset_add_order_form_state(state)
        state.pop(ORDER_ADD_RESET_PENDING_KEY, None)
        changed = True
    if state.get(ORDER_CONVERT_RESET_PENDING_KEY):
        reset_convert_order_form_state(state)
        state.pop(ORDER_CONVERT_RESET_PENDING_KEY, None)
        changed = True
    pending_page_mode = state.pop(ORDER_PENDING_PAGE_MODE_KEY, None)
    if pending_page_mode in ORDER_PAGE_MODES:
        state["order_page_mode"] = pending_page_mode
        changed = True
    return changed


def complete_order_creation_success(
    state: MutableMapping[str, Any],
    *,
    order_id: int,
    flash_message: str,
    source: str,
) -> None:
    state["selected_order_id"] = order_id
    mark_order_form_reset_pending(
        state,
        add=source == "add",
        convert=source == "convert",
        page_mode=ORDER_PAGE_DETAIL,
    )
    set_flash_message(state, flash_message)


def _row_key(prefix: str) -> str:
    return "convert_item_rows" if prefix == "convert" else "order_item_rows"


def add_order_item_row(state: MutableMapping[str, Any], *, prefix: str = "order") -> None:
    initialize_order_form_state(state)
    key = _row_key(prefix)
    rows = list(state.get(key) or [])
    rows.append(deepcopy(DEFAULT_ORDER_ITEM_ROW))
    state[key] = rows


def remove_order_item_row(state: MutableMapping[str, Any], index: int, *, prefix: str = "order") -> None:
    initialize_order_form_state(state)
    key = _row_key(prefix)
    rows = list(state.get(key) or [])
    if 0 <= index < len(rows):
        rows.pop(index)
    state[key] = rows or [deepcopy(DEFAULT_ORDER_ITEM_ROW)]


def update_order_item_row(state: MutableMapping[str, Any], index: int, field_name: str, value: Any, *, prefix: str = "order") -> None:
    initialize_order_form_state(state)
    key = _row_key(prefix)
    rows = list(state.get(key) or [])
    if 0 <= index < len(rows):
        row = dict(rows[index])
        row[field_name] = value
        rows[index] = row
        state[key] = rows


def set_selected_order_id(state: MutableMapping[str, Any], order_id: Optional[int]) -> None:
    state["selected_order_id"] = order_id


def selected_order_id(state: MutableMapping[str, Any]) -> Optional[int]:
    initialize_order_form_state(state)
    value = state.get("selected_order_id")
    return int(value) if value is not None else None


def set_order_page_mode(state: MutableMapping[str, Any], mode: str) -> None:
    if mode not in ORDER_PAGE_MODES:
        raise ValueError("Unsupported order page mode.")
    state["order_page_mode"] = mode


def order_page_mode(state: MutableMapping[str, Any]) -> str:
    initialize_order_form_state(state)
    mode = state.get("order_page_mode", ORDER_PAGE_BROWSE)
    return str(mode) if mode in ORDER_PAGE_MODES else ORDER_PAGE_BROWSE


def sync_order_related_selections(
    state: MutableMapping[str, Any],
    *,
    valid_location_ids: set[int],
    valid_contact_ids: set[int],
    valid_opportunity_ids: set[int],
    prefix: str = "order",
) -> None:
    initialize_order_form_state(state)
    if state.get(f"{prefix}_location_id") not in valid_location_ids:
        state[f"{prefix}_location_id"] = None
    if state.get(f"{prefix}_contact_id") not in valid_contact_ids:
        state[f"{prefix}_contact_id"] = None
    if prefix == "order" and state.get("order_opportunity_id") not in valid_opportunity_ids:
        state["order_opportunity_id"] = None


def normalize_date_value(value: object) -> Optional[date]:
    return value if isinstance(value, date) else None
