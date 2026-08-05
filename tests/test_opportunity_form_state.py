from copy import deepcopy
from dataclasses import dataclass

from app.form_state import ADD_COMPANY_DEFAULTS, ADD_CONTACT_DEFAULTS, pop_flash_message
from app.opportunity_form_state import (
    ADD_OPPORTUNITY_DEFAULTS,
    ADD_OPPORTUNITY_FORM_DEFAULTS,
    OPPORTUNITY_FORM_RESET_PENDING_KEY,
    OPPORTUNITY_PAGE_ADD,
    OPPORTUNITY_PAGE_BROWSE,
    OPPORTUNITY_PAGE_DETAIL,
    OPPORTUNITY_PENDING_PAGE_MODE_KEY,
    add_product_row,
    apply_pending_opportunity_form_reset,
    complete_opportunity_creation_success,
    initialize_opportunity_form_state,
    opportunity_page_mode,
    opportunity_form_snapshot,
    remove_product_row,
    reset_opportunity_form_state_after_success,
    selected_opportunity_id,
    set_opportunity_errors,
    set_opportunity_page_mode,
    set_selected_opportunity_id,
    sync_company_related_selections,
    update_product_row,
)
from app.opportunity_ui_helpers import opportunity_created_message


@dataclass(frozen=True)
class FakeCreatedOpportunityResult:
    opportunity_id: int
    opportunity_name: str
    company_id: int
    company_name: str


class ProtectedWidgetState(dict):
    def __init__(self, protected_keys: set[str], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.protected_keys = protected_keys

    def __setitem__(self, key, value) -> None:
        if key in self.protected_keys:
            raise AssertionError(f"Widget key {key} was modified after instantiation.")
        super().__setitem__(key, value)

    def __delitem__(self, key) -> None:
        if key in self.protected_keys:
            raise AssertionError(f"Widget key {key} was deleted after instantiation.")
        super().__delitem__(key)


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
    state["selected_opportunity_id"] = 77
    state["opportunity_page_mode"] = OPPORTUNITY_PAGE_ADD
    set_opportunity_errors(state, {"name": "Opportunity name is required."})

    snapshot = opportunity_form_snapshot(state)

    assert snapshot["opportunity_name"] == "Account review"
    assert snapshot["opportunity_next_action"] == "Call owner"
    assert snapshot["opportunity_errors"] == {"name": "Opportunity name is required."}
    assert selected_opportunity_id(state) == 77
    assert opportunity_page_mode(state) == OPPORTUNITY_PAGE_ADD
    assert "flash_message" not in state


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
    assert opportunity_page_mode(state) == OPPORTUNITY_PAGE_DETAIL


def test_selected_opportunity_id_persists() -> None:
    state = {}
    set_selected_opportunity_id(state, 99)

    assert selected_opportunity_id(state) == 99


def test_page_mode_defaults_to_browse_and_can_switch_to_detail() -> None:
    state = {}
    initialize_opportunity_form_state(state)

    assert opportunity_page_mode(state) == OPPORTUNITY_PAGE_BROWSE

    set_opportunity_page_mode(state, OPPORTUNITY_PAGE_ADD)
    assert opportunity_page_mode(state) == OPPORTUNITY_PAGE_ADD

    set_opportunity_page_mode(state, OPPORTUNITY_PAGE_DETAIL)
    assert opportunity_page_mode(state) == OPPORTUNITY_PAGE_DETAIL


def test_complete_opportunity_creation_success_sets_flash_selected_id_and_detail_mode() -> None:
    state = {}
    initialize_opportunity_form_state(state)
    state["opportunity_name"] = "Mobile & Internet Upgrade"
    update_product_row(state, 0, "product_code", "BUSINESS_MOBILE")

    complete_opportunity_creation_success(
        state,
        opportunity_id=55,
        flash_message='✅ Opportunity "Mobile & Internet Upgrade" created successfully for Sunshine Plumbing LLC.',
    )

    assert state["selected_opportunity_id"] == 55
    assert state[OPPORTUNITY_FORM_RESET_PENDING_KEY] is True
    assert state[OPPORTUNITY_PENDING_PAGE_MODE_KEY] == OPPORTUNITY_PAGE_DETAIL
    assert opportunity_page_mode(state) == OPPORTUNITY_PAGE_BROWSE
    assert state["opportunity_name"] == "Mobile & Internet Upgrade"
    assert state["opportunity_product_rows"][0]["product_code"] == "BUSINESS_MOBILE"
    assert state["flash_message"] == '✅ Opportunity "Mobile & Internet Upgrade" created successfully for Sunshine Plumbing LLC.'


def test_apply_pending_reset_clears_form_and_opens_detail() -> None:
    state = {
        "opportunity_company_id": 3,
        "opportunity_location_id": 4,
        "opportunity_contact_id": 5,
        "opportunity_name": "Mobile & Internet Upgrade",
        "opportunity_next_action": "Call owner",
        "opportunity_product_rows": [{"product_code": "BUSINESS_MOBILE", "estimated_quantity": 8}],
        "opportunity_errors": {"name": "Required"},
        "selected_opportunity_id": 55,
        "opportunity_page_mode": OPPORTUNITY_PAGE_ADD,
        "opportunity_browse_search": "sunshine",
        "flash_message": '✅ Opportunity "Mobile & Internet Upgrade" created successfully for Sunshine Plumbing LLC.',
        "opportunity_product_row_0_product": "BUSINESS_MOBILE",
        "opportunity_product_row_0_quantity": 8,
        "opportunity_product_row_0_mrr": "400.00",
        "opportunity_product_row_0_interest": "High",
        "opportunity_product_row_0_notes": "Owner asked for pricing",
    }
    complete_opportunity_creation_success(
        state,
        opportunity_id=55,
        flash_message='✅ Opportunity "Mobile & Internet Upgrade" created successfully for Sunshine Plumbing LLC.',
    )

    assert apply_pending_opportunity_form_reset(state) is True

    for key, value in ADD_OPPORTUNITY_FORM_DEFAULTS.items():
        assert state[key] == value
    assert state["selected_opportunity_id"] == 55
    assert opportunity_page_mode(state) == OPPORTUNITY_PAGE_DETAIL
    assert state["opportunity_browse_search"] == "sunshine"
    assert state["flash_message"] == '✅ Opportunity "Mobile & Internet Upgrade" created successfully for Sunshine Plumbing LLC.'
    assert OPPORTUNITY_FORM_RESET_PENDING_KEY not in state
    assert OPPORTUNITY_PENDING_PAGE_MODE_KEY not in state
    assert not any(key.startswith("opportunity_product_row_") for key in state)


def test_pending_reset_noops_when_not_marked() -> None:
    state = {"opportunity_name": "Keep me", "opportunity_page_mode": OPPORTUNITY_PAGE_ADD}

    assert apply_pending_opportunity_form_reset(state) is False

    assert state["opportunity_name"] == "Keep me"
    assert opportunity_page_mode(state) == OPPORTUNITY_PAGE_ADD


def test_successful_creation_does_not_directly_mutate_instantiated_widget_keys() -> None:
    protected_keys = set(ADD_OPPORTUNITY_FORM_DEFAULTS) | {"opportunity_page_mode"}
    state = ProtectedWidgetState(protected_keys)
    dict.update(
        state,
        {
            "opportunity_company_id": 3,
            "opportunity_name": "Mobile & Internet Upgrade",
            "opportunity_page_mode": OPPORTUNITY_PAGE_ADD,
        },
    )

    complete_opportunity_creation_success(
        state,
        opportunity_id=55,
        flash_message='✅ Opportunity "Mobile & Internet Upgrade" created successfully for Sunshine Plumbing LLC.',
    )

    assert state["selected_opportunity_id"] == 55
    assert state[OPPORTUNITY_FORM_RESET_PENDING_KEY] is True
    assert state[OPPORTUNITY_PENDING_PAGE_MODE_KEY] == OPPORTUNITY_PAGE_DETAIL
    assert state["opportunity_company_id"] == 3
    assert state["opportunity_name"] == "Mobile & Internet Upgrade"
    assert state["opportunity_page_mode"] == OPPORTUNITY_PAGE_ADD


def test_creation_flash_message_renders_once() -> None:
    state = {}
    complete_opportunity_creation_success(
        state,
        opportunity_id=55,
        flash_message='✅ Opportunity "Mobile & Internet Upgrade" created successfully for Sunshine Plumbing LLC.',
    )

    assert pop_flash_message(state) == (
        '✅ Opportunity "Mobile & Internet Upgrade" created successfully for Sunshine Plumbing LLC.',
        "success",
    )
    assert pop_flash_message(state) is None


def test_creation_success_uses_scalar_result_without_storing_orm_objects() -> None:
    state = {}
    initialize_opportunity_form_state(state)
    created = FakeCreatedOpportunityResult(
        opportunity_id=72,
        opportunity_name="Mobile & Internet Upgrade",
        company_id=5,
        company_name="Sunshine Plumbing LLC",
    )

    complete_opportunity_creation_success(
        state,
        opportunity_id=created.opportunity_id,
        flash_message=opportunity_created_message(created.opportunity_name, created.company_name),
    )

    assert selected_opportunity_id(state) == 72
    assert state[OPPORTUNITY_FORM_RESET_PENDING_KEY] is True
    assert state["flash_message"] == '✅ Opportunity "Mobile & Internet Upgrade" created successfully for Sunshine Plumbing LLC.'
    assert all(not hasattr(value, "_sa_instance_state") for value in state.values())


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
