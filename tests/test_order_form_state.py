from app.enums import SaleStatus
from app.order_form_state import (
    DEFAULT_ORDER_ITEM_ROW,
    ORDER_PAGE_ADD,
    ORDER_PAGE_BROWSE,
    ORDER_PAGE_DETAIL,
    add_order_item_row,
    apply_pending_order_form_reset,
    complete_order_creation_success,
    initialize_order_form_state,
    order_page_mode,
    remove_order_item_row,
    selected_order_id,
    set_order_page_mode,
    set_selected_order_id,
    sync_order_related_selections,
    update_order_item_row,
)


def test_initialize_order_form_state_sets_add_convert_and_page_defaults() -> None:
    state: dict[str, object] = {}

    initialize_order_form_state(state)

    assert state["order_company_id"] is None
    assert state["convert_opportunity_id"] is None
    assert state["order_status"] == SaleStatus.DRAFT.value
    assert state["order_page_mode"] == ORDER_PAGE_BROWSE
    assert state["order_item_rows"] == [DEFAULT_ORDER_ITEM_ROW]


def test_order_item_row_mutators_are_scoped() -> None:
    state: dict[str, object] = {}
    initialize_order_form_state(state)

    add_order_item_row(state)
    update_order_item_row(state, 1, "product_code", "BUSINESS_MOBILE")
    remove_order_item_row(state, 0)

    assert state["order_item_rows"] == [{**DEFAULT_ORDER_ITEM_ROW, "product_code": "BUSINESS_MOBILE"}]
    assert state["convert_item_rows"] == [DEFAULT_ORDER_ITEM_ROW]


def test_deferred_success_reset_preserves_selected_order_and_uses_pending_page_mode() -> None:
    state: dict[str, object] = {
        "order_company_id": 1,
        "order_item_row_0_product": "BUSINESS_INTERNET",
        "order_browse_company_id": 1,
    }
    initialize_order_form_state(state)

    complete_order_creation_success(state, order_id=42, flash_message="created", source="add")
    assert state["selected_order_id"] == 42
    assert state["order_company_id"] == 1
    assert state["order_page_mode"] == ORDER_PAGE_BROWSE

    assert apply_pending_order_form_reset(state) is True

    assert state["selected_order_id"] == 42
    assert state["order_company_id"] is None
    assert state["order_page_mode"] == ORDER_PAGE_DETAIL
    assert "order_item_row_0_product" not in state
    assert state["order_browse_company_id"] == 1
    assert state["flash_message"] == "created"


def test_failed_submission_keeps_form_values() -> None:
    state: dict[str, object] = {"order_company_id": 7, "order_errors": {"company": "bad"}}
    initialize_order_form_state(state)

    assert apply_pending_order_form_reset(state) is False

    assert state["order_company_id"] == 7
    assert state["order_errors"] == {"company": "bad"}


def test_convert_reset_is_independent_from_add_form() -> None:
    state: dict[str, object] = {
        "order_company_id": 1,
        "convert_opportunity_id": 9,
        "convert_order_item_row_0_product": "BUSINESS_INTERNET",
    }
    initialize_order_form_state(state)

    complete_order_creation_success(state, order_id=55, flash_message="converted", source="convert")
    apply_pending_order_form_reset(state)

    assert state["selected_order_id"] == 55
    assert state["order_company_id"] == 1
    assert state["convert_opportunity_id"] is None
    assert "convert_order_item_row_0_product" not in state


def test_selection_and_page_mode_helpers() -> None:
    state: dict[str, object] = {}

    set_selected_order_id(state, 10)
    set_order_page_mode(state, ORDER_PAGE_ADD)

    assert selected_order_id(state) == 10
    assert order_page_mode(state) == ORDER_PAGE_ADD


def test_sync_order_related_selections_clears_invalid_related_ids() -> None:
    state: dict[str, object] = {"order_location_id": 1, "order_contact_id": 2, "order_opportunity_id": 3}
    initialize_order_form_state(state)

    sync_order_related_selections(
        state,
        valid_location_ids={4},
        valid_contact_ids={2},
        valid_opportunity_ids=set(),
    )

    assert state["order_location_id"] is None
    assert state["order_contact_id"] == 2
    assert state["order_opportunity_id"] is None
