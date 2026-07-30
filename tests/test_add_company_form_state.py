from app.form_state import (
    contact_form_key,
    initialize_add_company_form_state,
    initialize_contact_form_state,
    pop_flash_message,
    referral_fields_visible,
    reset_add_company_form_state,
    reset_contact_form_state,
    set_flash_message,
    validate_add_company_form_state,
    validate_contact_form_state,
)
from app.validation import LEAD_SOURCE_AE_FOUND, LEAD_SOURCE_REFERRAL


def valid_state() -> dict[str, object]:
    state: dict[str, object] = {}
    initialize_add_company_form_state(state)
    state.update(
        {
            "add_company_name": "Form State Co",
            "add_company_phone": "2321231234",
            "add_company_website": "example.com",
            "add_company_industry": "Plumbing",
            "add_company_lead_source": LEAD_SOURCE_AE_FOUND,
            "add_company_notes": "Keep this note",
        }
    )
    return state


def test_referral_selection_preserves_company_field_values() -> None:
    state = valid_state()
    state["add_company_lead_source"] = LEAD_SOURCE_REFERRAL

    assert referral_fields_visible(state["add_company_lead_source"]) is True
    assert state["add_company_name"] == "Form State Co"
    assert state["add_company_phone"] == "2321231234"
    assert state["add_company_notes"] == "Keep this note"


def test_ae_found_does_not_require_referral_partner() -> None:
    company_payload, partner_payload, errors = validate_add_company_form_state(valid_state())

    assert errors == {}
    assert partner_payload is None
    assert company_payload["referral_partner_id"] is None


def test_referral_requires_existing_or_new_referral_partner() -> None:
    state = valid_state()
    state["add_company_lead_source"] = LEAD_SOURCE_REFERRAL

    _, _, errors = validate_add_company_form_state(state)

    assert errors["referral"] == "Select an existing referral partner or add a new one."


def test_failed_validation_does_not_clear_form_state_values() -> None:
    state = valid_state()
    state["add_company_phone"] = "bad"

    _, _, errors = validate_add_company_form_state(state)

    assert errors["phone"] == "Public phone must contain digits only."
    assert state["add_company_name"] == "Form State Co"
    assert state["add_company_website"] == "example.com"


def test_successful_creation_helper_reset_clears_values() -> None:
    state = valid_state()

    reset_add_company_form_state(state)

    assert state["add_company_name"] == ""
    assert state["add_company_phone"] == ""
    assert state["add_company_industry"] == "Select industry"


def test_new_referral_partner_payload_requires_identity() -> None:
    state = valid_state()
    state["add_company_lead_source"] = LEAD_SOURCE_REFERRAL
    state["add_company_referral_mode"] = "Add new referral partner"

    _, partner_payload, errors = validate_add_company_form_state(state)

    assert partner_payload is not None
    assert errors["referral"] == "Referral partner information is incomplete."


def test_new_referral_partner_payload_accepts_identity() -> None:
    state = valid_state()
    state["add_company_lead_source"] = LEAD_SOURCE_REFERRAL
    state["add_company_referral_mode"] = "Add new referral partner"
    state["add_company_partner_org"] = "Local Chamber"

    company_payload, partner_payload, errors = validate_add_company_form_state(state)

    assert errors == {}
    assert company_payload["lead_source"] == LEAD_SOURCE_REFERRAL
    assert partner_payload is not None
    assert partner_payload["organization"] == "Local Chamber"


def test_setting_success_flash_message_stores_scalar_values() -> None:
    state: dict[str, object] = {}

    set_flash_message(state, "Company archived.")

    assert state == {"flash_message": "Company archived.", "flash_message_level": "success"}


def test_rendering_flash_message_clears_it_and_only_once() -> None:
    state: dict[str, object] = {}
    set_flash_message(state, "Company restored.", "success")

    assert pop_flash_message(state) == ("Company restored.", "success")
    assert pop_flash_message(state) is None
    assert state == {}


def test_contact_add_failure_preserves_other_form_values() -> None:
    state: dict[str, object] = {}
    prefix = "add_contact_1"
    initialize_contact_form_state(state, prefix)
    state[contact_form_key(prefix, "first_name")] = "Jamie"
    state[contact_form_key(prefix, "phone")] = "bad"
    state[contact_form_key(prefix, "email")] = "jamie@example.com"

    _, errors = validate_contact_form_state(state, prefix)

    assert errors["phone"] == "Contact phone must contain digits only."
    assert state[contact_form_key(prefix, "first_name")] == "Jamie"
    assert state[contact_form_key(prefix, "email")] == "jamie@example.com"


def test_contact_email_failure_preserves_form_values() -> None:
    state: dict[str, object] = {}
    prefix = "add_contact_2"
    initialize_contact_form_state(state, prefix)
    state[contact_form_key(prefix, "first_name")] = "Jamie"
    state[contact_form_key(prefix, "email")] = "some"
    state[contact_form_key(prefix, "notes")] = "Preserve me"

    _, errors = validate_contact_form_state(state, prefix)

    assert errors["email"] == "Enter a valid email address, such as name@company.com."
    assert state[contact_form_key(prefix, "notes")] == "Preserve me"


def test_contact_blank_names_fail_and_preserve_values() -> None:
    state: dict[str, object] = {}
    prefix = "add_contact_3"
    initialize_contact_form_state(state, prefix)
    state[contact_form_key(prefix, "email")] = "mary@company.com"

    _, errors = validate_contact_form_state(state, prefix)

    assert errors["name"] == "Enter at least a first name or last name."
    assert state[contact_form_key(prefix, "email")] == "mary@company.com"


def test_contact_other_title_requires_custom_title() -> None:
    state: dict[str, object] = {}
    prefix = "add_contact_4"
    initialize_contact_form_state(state, prefix)
    state[contact_form_key(prefix, "first_name")] = "Jamie"
    state[contact_form_key(prefix, "title_selection")] = "Other"

    _, errors = validate_contact_form_state(state, prefix)

    assert errors["title"] == "Enter a title when Other is selected."


def test_contact_edit_failure_preserves_other_form_values() -> None:
    state: dict[str, object] = {}
    prefix = "edit_contact_10"
    initialize_contact_form_state(state, prefix, {"first_name": "Morgan", "phone": "2321231234"})
    state[contact_form_key(prefix, "title_selection")] = "Owner"
    state[contact_form_key(prefix, "phone")] = "232-123-1234"

    _, errors = validate_contact_form_state(state, prefix)

    assert errors["phone"] == "Contact phone must contain digits only."
    assert state[contact_form_key(prefix, "title_selection")] == "Owner"


def test_successful_contact_creation_clears_intended_form_state() -> None:
    state: dict[str, object] = {}
    prefix = "add_contact_1"
    initialize_contact_form_state(state, prefix)
    state[contact_form_key(prefix, "first_name")] = "Jamie"
    state[contact_form_key(prefix, "phone")] = "2321231234"

    reset_contact_form_state(state, prefix)

    assert state[contact_form_key(prefix, "first_name")] == ""
    assert state[contact_form_key(prefix, "phone")] == ""
