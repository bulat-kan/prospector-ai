from copy import deepcopy
from datetime import date
from typing import Any, MutableMapping, Optional

from app.enums import OpportunityStage
from app.form_state import set_flash_message


OPPORTUNITY_FORM_RESET_PENDING_KEY = "opportunity_form_reset_pending"
OPPORTUNITY_PENDING_PAGE_MODE_KEY = "opportunity_pending_page_mode"
OPPORTUNITY_PRODUCT_ROW_WIDGET_PREFIX = "opportunity_product_row"

DEFAULT_PRODUCT_ROW: dict[str, Any] = {
    "product_code": None,
    "estimated_quantity": 1,
    "estimated_incremental_mrr": "0.00",
    "interest_level": "Unknown",
    "notes": "",
}

ADD_OPPORTUNITY_FORM_DEFAULTS: dict[str, Any] = {
    "opportunity_company_id": None,
    "opportunity_location_id": None,
    "opportunity_contact_id": None,
    "opportunity_name": "",
    "opportunity_stage": OpportunityStage.NEW.value,
    "opportunity_expected_close_date": None,
    "opportunity_next_action": "",
    "opportunity_next_action_date": None,
    "opportunity_lost_reason": "",
    "opportunity_estimated_mrr": "0.00",
    "opportunity_internet_probability": 0,
    "opportunity_revenue_potential_score": 0,
    "opportunity_cross_sell_score": 0,
    "opportunity_priority_score": 0,
    "opportunity_notes": "",
    "opportunity_score_reason": "",
    "opportunity_product_rows": [deepcopy(DEFAULT_PRODUCT_ROW)],
    "opportunity_errors": {},
}

OPPORTUNITY_PAGE_STATE_DEFAULTS: dict[str, Any] = {
    "selected_opportunity_id": None,
    "selected_opportunity_product_id": None,
    "opportunity_page_mode": "Browse opportunities",
}

OPPORTUNITY_PAGE_BROWSE = "Browse opportunities"
OPPORTUNITY_PAGE_ADD = "Add opportunity"
OPPORTUNITY_PAGE_DETAIL = "Opportunity detail"
OPPORTUNITY_PAGE_MODES = (
    OPPORTUNITY_PAGE_BROWSE,
    OPPORTUNITY_PAGE_ADD,
    OPPORTUNITY_PAGE_DETAIL,
)

ADD_OPPORTUNITY_DEFAULTS: dict[str, Any] = {
    **ADD_OPPORTUNITY_FORM_DEFAULTS,
    **OPPORTUNITY_PAGE_STATE_DEFAULTS,
}


def initialize_opportunity_form_state(state: MutableMapping[str, Any]) -> None:
    for key, value in ADD_OPPORTUNITY_DEFAULTS.items():
        state.setdefault(key, deepcopy(value))


def _clear_product_row_widget_keys(state: MutableMapping[str, Any]) -> None:
    for key in tuple(state):
        if str(key).startswith(f"{OPPORTUNITY_PRODUCT_ROW_WIDGET_PREFIX}_"):
            del state[key]
    state.pop(f"{OPPORTUNITY_PRODUCT_ROW_WIDGET_PREFIX}_add", None)


def reset_opportunity_form_state(state: MutableMapping[str, Any]) -> None:
    for key, value in ADD_OPPORTUNITY_FORM_DEFAULTS.items():
        state[key] = deepcopy(value)
    _clear_product_row_widget_keys(state)


def reset_opportunity_form_state_after_success(state: MutableMapping[str, Any], selected_opportunity_id: int) -> None:
    reset_opportunity_form_state(state)
    state["selected_opportunity_id"] = selected_opportunity_id
    state["opportunity_page_mode"] = OPPORTUNITY_PAGE_DETAIL
    state["opportunity_errors"] = {}


def mark_opportunity_form_reset_pending(state: MutableMapping[str, Any], *, page_mode: str = OPPORTUNITY_PAGE_DETAIL) -> None:
    state[OPPORTUNITY_FORM_RESET_PENDING_KEY] = True
    state[OPPORTUNITY_PENDING_PAGE_MODE_KEY] = page_mode


def apply_pending_opportunity_form_reset(state: MutableMapping[str, Any]) -> bool:
    initialize_opportunity_form_state(state)
    if not state.get(OPPORTUNITY_FORM_RESET_PENDING_KEY):
        return False

    reset_opportunity_form_state(state)
    pending_page_mode = state.pop(OPPORTUNITY_PENDING_PAGE_MODE_KEY, None)
    if pending_page_mode in OPPORTUNITY_PAGE_MODES:
        state["opportunity_page_mode"] = pending_page_mode
    state.pop(OPPORTUNITY_FORM_RESET_PENDING_KEY, None)
    return True


def complete_opportunity_creation_success(
    state: MutableMapping[str, Any],
    *,
    opportunity_id: int,
    flash_message: str,
) -> None:
    state["selected_opportunity_id"] = opportunity_id
    mark_opportunity_form_reset_pending(state, page_mode=OPPORTUNITY_PAGE_DETAIL)
    set_flash_message(state, flash_message)


def opportunity_form_snapshot(state: MutableMapping[str, Any]) -> dict[str, Any]:
    initialize_opportunity_form_state(state)
    return {key: deepcopy(state.get(key)) for key in ADD_OPPORTUNITY_DEFAULTS}


def set_opportunity_errors(state: MutableMapping[str, Any], errors: dict[str, str]) -> None:
    state["opportunity_errors"] = errors


def add_product_row(state: MutableMapping[str, Any]) -> None:
    initialize_opportunity_form_state(state)
    rows = list(state.get("opportunity_product_rows") or [])
    rows.append(deepcopy(DEFAULT_PRODUCT_ROW))
    state["opportunity_product_rows"] = rows


def remove_product_row(state: MutableMapping[str, Any], index: int) -> None:
    initialize_opportunity_form_state(state)
    rows = list(state.get("opportunity_product_rows") or [])
    if 0 <= index < len(rows):
        rows.pop(index)
    state["opportunity_product_rows"] = rows or [deepcopy(DEFAULT_PRODUCT_ROW)]


def update_product_row(state: MutableMapping[str, Any], index: int, field_name: str, value: Any) -> None:
    initialize_opportunity_form_state(state)
    rows = list(state.get("opportunity_product_rows") or [])
    if 0 <= index < len(rows):
        row = dict(rows[index])
        row[field_name] = value
        rows[index] = row
        state["opportunity_product_rows"] = rows


def sync_company_related_selections(
    state: MutableMapping[str, Any],
    *,
    valid_location_ids: set[int],
    valid_contact_ids: set[int],
) -> None:
    initialize_opportunity_form_state(state)
    if state.get("opportunity_location_id") not in valid_location_ids:
        state["opportunity_location_id"] = None
    if state.get("opportunity_contact_id") not in valid_contact_ids:
        state["opportunity_contact_id"] = None


def selected_opportunity_id(state: MutableMapping[str, Any]) -> Optional[int]:
    initialize_opportunity_form_state(state)
    value = state.get("selected_opportunity_id")
    return int(value) if value is not None else None


def set_selected_opportunity_id(state: MutableMapping[str, Any], opportunity_id: Optional[int]) -> None:
    state["selected_opportunity_id"] = opportunity_id


def opportunity_page_mode(state: MutableMapping[str, Any]) -> str:
    initialize_opportunity_form_state(state)
    mode = state.get("opportunity_page_mode", OPPORTUNITY_PAGE_BROWSE)
    return str(mode) if mode in OPPORTUNITY_PAGE_MODES else OPPORTUNITY_PAGE_BROWSE


def set_opportunity_page_mode(state: MutableMapping[str, Any], mode: str) -> None:
    if mode not in OPPORTUNITY_PAGE_MODES:
        raise ValueError("Unsupported opportunity page mode.")
    state["opportunity_page_mode"] = mode


def normalize_date_value(value: object) -> Optional[date]:
    return value if isinstance(value, date) else None
