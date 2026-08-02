from app.constants import REFERRAL_PHONE_MAX_CHARS
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


REFERRAL_EMAIL_ERROR = "Enter a valid referral partner email address, such as name@company.com."


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


def referral_state() -> dict[str, object]:
    state = valid_state()
    state.update(
        {
            "add_company_lead_source": LEAD_SOURCE_REFERRAL,
            "add_company_referral_mode": "Add new referral partner",
            "add_company_partner_first": "Nancy",
            "add_company_partner_last": "Carter",
            "add_company_partner_org": "Local Chamber",
            "add_company_partner_role": "President",
            "add_company_partner_reference": "SP-1",
            "add_company_partner_notes": "Partner note",
            "add_company_notes": "Company note",
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
    assert errors["referral"] == "At least one referral partner name, organization, email, or phone value is required."


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


def test_new_referral_partner_invalid_phone_preserves_form_values() -> None:
    state = referral_state()
    state["add_company_partner_phone"] = "232-123-1234"
    state["add_company_notes"] = "Do not clear me"

    _, partner_payload, errors = validate_add_company_form_state(state)

    assert partner_payload is not None
    assert errors["referral_phone"] == "Referral partner phone must contain digits only."
    assert state["add_company_partner_org"] == "Local Chamber"
    assert state["add_company_notes"] == "Do not clear me"


def test_new_referral_partner_email_is_normalized_in_payload() -> None:
    state = referral_state()
    state["add_company_partner_email"] = " PARTNER@EXAMPLE.COM "

    _, partner_payload, errors = validate_add_company_form_state(state)

    assert errors == {}
    assert partner_payload is not None
    assert partner_payload["email"] == "partner@example.com"


def test_referral_phone_widget_configuration_limits_input_to_ten_characters() -> None:
    assert REFERRAL_PHONE_MAX_CHARS == 10


def test_new_referral_partner_long_phone_sets_field_error() -> None:
    state = referral_state()
    state["add_company_partner_phone"] = "3434343434334343434343"

    _, _, errors = validate_add_company_form_state(state)

    assert errors["referral_phone"] == "Referral partner phone must contain exactly 10 digits."


def test_new_referral_partner_phone_with_letters_sets_field_error() -> None:
    state = referral_state()
    state["add_company_partner_phone"] = "343abc3434"

    _, _, errors = validate_add_company_form_state(state)

    assert errors["referral_phone"] == "Referral partner phone must contain digits only."


def test_new_referral_partner_phone_with_symbols_sets_field_error() -> None:
    state = referral_state()
    state["add_company_partner_phone"] = "343-434-3434"

    _, _, errors = validate_add_company_form_state(state)

    assert errors["referral_phone"] == "Referral partner phone must contain digits only."


def test_new_referral_partner_email_1_dot_com_sets_field_error() -> None:
    state = referral_state()
    state["add_company_partner_email"] = "1.com"

    _, _, errors = validate_add_company_form_state(state)

    assert errors["referral_email"] == REFERRAL_EMAIL_ERROR


def test_new_referral_partner_email_some_sets_field_error() -> None:
    state = referral_state()
    state["add_company_partner_email"] = "some"

    _, _, errors = validate_add_company_form_state(state)

    assert errors["referral_email"] == REFERRAL_EMAIL_ERROR


def test_valid_referral_phone_clears_phone_error() -> None:
    state = referral_state()
    state["add_company_partner_phone"] = "3434343434"

    _, partner_payload, errors = validate_add_company_form_state(state)

    assert "referral_phone" not in errors
    assert partner_payload is not None
    assert partner_payload["phone"] == "3434343434"


def test_valid_referral_email_clears_email_error() -> None:
    state = referral_state()
    state["add_company_partner_email"] = "Nancy@MarioBros.COM"

    _, partner_payload, errors = validate_add_company_form_state(state)

    assert "referral_email" not in errors
    assert partner_payload is not None
    assert partner_payload["email"] == "nancy@mariobros.com"


def test_invalid_referral_email_preserves_company_values() -> None:
    state = referral_state()
    state["add_company_partner_email"] = "1.com"

    validate_add_company_form_state(state)

    assert state["add_company_name"] == "Form State Co"
    assert state["add_company_lead_source"] == LEAD_SOURCE_REFERRAL
    assert state["add_company_notes"] == "Company note"


def test_invalid_referral_phone_preserves_partner_fields() -> None:
    state = referral_state()
    state["add_company_partner_phone"] = "bad"

    validate_add_company_form_state(state)

    assert state["add_company_referral_mode"] == "Add new referral partner"
    assert state["add_company_partner_first"] == "Nancy"
    assert state["add_company_partner_org"] == "Local Chamber"
    assert state["add_company_partner_notes"] == "Partner note"


def test_invalid_referral_email_preserves_partner_fields() -> None:
    state = referral_state()
    state["add_company_partner_email"] = "some"

    validate_add_company_form_state(state)

    assert state["add_company_referral_mode"] == "Add new referral partner"
    assert state["add_company_partner_last"] == "Carter"
    assert state["add_company_partner_reference"] == "SP-1"


def test_both_invalid_referral_phone_and_email_are_reported() -> None:
    state = referral_state()
    state["add_company_partner_phone"] = "3434343434334343434343"
    state["add_company_partner_email"] = "1.com"

    _, _, errors = validate_add_company_form_state(state)

    assert errors["referral_phone"] == "Referral partner phone must contain exactly 10 digits."
    assert errors["referral_email"] == REFERRAL_EMAIL_ERROR


def test_reset_clears_referral_field_error_state() -> None:
    state = referral_state()
    state["add_company_referral_phone_error"] = "Phone error"
    state["add_company_referral_email_error"] = "Email error"

    reset_add_company_form_state(state)

    assert state["add_company_referral_phone_error"] == ""
    assert state["add_company_referral_email_error"] == ""


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
