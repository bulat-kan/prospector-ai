from copy import deepcopy

from app.form_state import ADD_COMPANY_DEFAULTS, ADD_CONTACT_DEFAULTS
from app.opportunity_form_state import (
    ADD_OPPORTUNITY_DEFAULTS,
    add_product_row,
    initialize_opportunity_form_state,
    opportunity_form_snapshot,
    remove_product_row,
    reset_opportunity_form_state_after_success,
    selected_opportunity_id,
    set_opportunity_errors,
    set_selected_opportunity_id,
    sync_company_related_selections,
    update_product_row,
)


def test_initial_state_is_valid() -> None:
    state = {}
    initialize_opportunity_form_state(state)

    assert set(ADD_OPPORTUNITY_DEFAULTS) <= set(state)
    assert state["opportunity_name"] == ""
    assert len(state["opportunity_product_rows"]) == 1


def test_values_preserved_after_validation_failure() -> None:
    state = {}
    initialize_opportunity_form_state(state)
    state["opportunity_name"] = "Account review"
    state["opportunity_next_action"] = "Call owner"
    set_opportunity_errors(state, {"name": "Opportunity name is required."})

    snapshot = opportunity_form_snapshot(state)

    assert snapshot["opportunity_name"] == "Account review"
    assert snapshot["opportunity_next_action"] == "Call owner"
    assert snapshot["opportunity_errors"] == {"name": "Opportunity name is required."}


def test_product_rows_preserved_after_validation_failure() -> None:
    state = {}
    initialize_opportunity_form_state(state)
    update_product_row(state, 0, "product_code", "BUSINESS_MOBILE")
    update_product_row(state, 0, "estimated_quantity", 8)
    set_opportunity_errors(state, {"product_0": "This product is already included in the opportunity."})

    assert state["opportunity_product_rows"][0]["product_code"] == "BUSINESS_MOBILE"
    assert state["opportunity_product_rows"][0]["estimated_quantity"] == 8


def test_add_and_remove_unsaved_product_row() -> None:
    state = {}
    initialize_opportunity_form_state(state)
    add_product_row(state)
    update_product_row(state, 1, "product_code", "SEASONAL_SPORTS")

    assert len(state["opportunity_product_rows"]) == 2
    assert state["opportunity_product_rows"][1]["product_code"] == "SEASONAL_SPORTS"

    remove_product_row(state, 1)

    assert len(state["opportunity_product_rows"]) == 1


def test_successful_creation_resets_form_state_and_preserves_selected_opportunity() -> None:
    state = {}
    initialize_opportunity_form_state(state)
    state["opportunity_name"] = "Before reset"
    reset_opportunity_form_state_after_success(state, 42)

    assert state["opportunity_name"] == ""
    assert selected_opportunity_id(state) == 42


def test_selected_opportunity_id_persists() -> None:
    state = {}
    set_selected_opportunity_id(state, 99)

    assert selected_opportunity_id(state) == 99


def test_invalid_location_and_contact_selection_resets() -> None:
    state = {}
    initialize_opportunity_form_state(state)
    state["opportunity_location_id"] = 10
    state["opportunity_contact_id"] = 20

    sync_company_related_selections(state, valid_location_ids={1}, valid_contact_ids={2})

    assert state["opportunity_location_id"] is None
    assert state["opportunity_contact_id"] is None


def test_valid_location_and_contact_selection_stays() -> None:
    state = {}
    initialize_opportunity_form_state(state)
    state["opportunity_location_id"] = 10
    state["opportunity_contact_id"] = 20

    sync_company_related_selections(state, valid_location_ids={10}, valid_contact_ids={20})

    assert state["opportunity_location_id"] == 10
    assert state["opportunity_contact_id"] == 20


def test_referral_company_and_contact_form_keys_remain_unaffected() -> None:
    opportunity_keys = set(ADD_OPPORTUNITY_DEFAULTS)

    assert opportunity_keys.isdisjoint(ADD_COMPANY_DEFAULTS)
    assert opportunity_keys.isdisjoint(ADD_CONTACT_DEFAULTS)


def test_product_row_copies_are_independent() -> None:
    state = {}
    initialize_opportunity_form_state(state)
    original = deepcopy(state["opportunity_product_rows"][0])
    add_product_row(state)
    update_product_row(state, 1, "product_code", "EVERPASS")

    assert state["opportunity_product_rows"][0] == original
    assert state["opportunity_product_rows"][1]["product_code"] == "EVERPASS"
