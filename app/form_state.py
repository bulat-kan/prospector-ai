from typing import Any, MutableMapping, Optional

from app.validation import (
    CONTACT_TITLE_PLACEHOLDER,
    CONTACT_TITLE_OTHER,
    INDUSTRY_OTHER,
    INDUSTRY_PLACEHOLDER,
    LEAD_SOURCE_AE_FOUND,
    LEAD_SOURCE_REFERRAL,
    clean_optional_text,
    normalize_company_phone,
    normalize_contact_phone,
    normalize_contact_title,
    normalize_email,
    normalize_name,
    normalize_website,
    validate_company_name,
    validate_industry_selection,
    validate_lead_source,
    validate_contact_identity,
    validate_decision_role,
    validate_referral_partner_identity,
)


ADD_COMPANY_DEFAULTS: dict[str, Any] = {
    "add_company_name": "",
    "add_company_phone": "",
    "add_company_website": "",
    "add_company_industry": INDUSTRY_PLACEHOLDER,
    "add_company_other_industry": "",
    "add_company_lead_source": None,
    "add_company_notes": "",
    "add_company_referral_mode": "Select existing referral partner",
    "add_company_referral_partner_id": None,
    "add_company_partner_first": "",
    "add_company_partner_last": "",
    "add_company_partner_org": "",
    "add_company_partner_role": "",
    "add_company_partner_phone": "",
    "add_company_partner_email": "",
    "add_company_partner_registered": False,
    "add_company_partner_reference": "",
    "add_company_partner_notes": "",
}

ADD_CONTACT_DEFAULTS: dict[str, Any] = {
    "first_name": "",
    "last_name": "",
    "title_selection": CONTACT_TITLE_PLACEHOLDER,
    "other_title": "",
    "location_id": None,
    "phone": "",
    "email": "",
    "decision_role": "UNKNOWN",
    "is_primary_contact": False,
    "notes": "",
}


def initialize_add_company_form_state(state: MutableMapping[str, Any]) -> None:
    for key, value in ADD_COMPANY_DEFAULTS.items():
        state.setdefault(key, value)


def reset_add_company_form_state(state: MutableMapping[str, Any]) -> None:
    for key, value in ADD_COMPANY_DEFAULTS.items():
        state[key] = value


def referral_fields_visible(lead_source: Optional[str]) -> bool:
    return validate_lead_source(lead_source) == LEAD_SOURCE_REFERRAL


def add_company_state_snapshot(state: MutableMapping[str, Any]) -> dict[str, Any]:
    initialize_add_company_form_state(state)
    return {key: state.get(key) for key in ADD_COMPANY_DEFAULTS}


def validate_add_company_form_state(state: MutableMapping[str, Any]) -> tuple[dict[str, Any], Optional[dict[str, Any]], dict[str, str]]:
    values = add_company_state_snapshot(state)
    errors: dict[str, str] = {}
    company_payload: dict[str, Any] = {}
    partner_payload: Optional[dict[str, Any]] = None

    try:
        company_payload["name"] = validate_company_name(values["add_company_name"])
    except ValueError as exc:
        errors["name"] = str(exc)

    try:
        company_payload["main_phone"] = normalize_company_phone(values["add_company_phone"])
    except ValueError as exc:
        errors["phone"] = str(exc)

    try:
        company_payload["website"] = normalize_website(values["add_company_website"])
    except ValueError as exc:
        errors["website"] = str(exc)

    try:
        company_payload["industry"] = validate_industry_selection(
            values["add_company_industry"],
            values["add_company_other_industry"],
        )
    except ValueError as exc:
        errors["industry"] = str(exc)

    try:
        lead_source = validate_lead_source(values["add_company_lead_source"])
        if lead_source is None:
            raise ValueError("Please select a lead source.")
        company_payload["lead_source"] = lead_source
    except ValueError as exc:
        errors["lead_source"] = str(exc)
        lead_source = None

    company_payload["notes"] = clean_optional_text(values["add_company_notes"])

    if lead_source == LEAD_SOURCE_AE_FOUND:
        company_payload["referral_partner_id"] = None
    elif lead_source == LEAD_SOURCE_REFERRAL:
        if values["add_company_referral_mode"] == "Select existing referral partner":
            referral_partner_id = values["add_company_referral_partner_id"]
            if referral_partner_id is None:
                errors["referral"] = "Select an existing referral partner or add a new one."
            company_payload["referral_partner_id"] = referral_partner_id
        else:
            partner_payload = {
                "first_name": values["add_company_partner_first"],
                "last_name": values["add_company_partner_last"],
                "organization": values["add_company_partner_org"],
                "role_or_type": values["add_company_partner_role"],
                "phone": values["add_company_partner_phone"],
                "email": values["add_company_partner_email"],
                "is_registered_spectrum_partner": bool(values["add_company_partner_registered"]),
                "spectrum_partner_reference": values["add_company_partner_reference"],
                "notes": values["add_company_partner_notes"],
            }
            try:
                validate_referral_partner_identity(
                    partner_payload["first_name"],
                    partner_payload["last_name"],
                    partner_payload["organization"],
                    partner_payload["phone"],
                    partner_payload["email"],
                )
            except ValueError:
                errors["referral"] = "Referral partner information is incomplete."

    return company_payload, partner_payload, errors


def set_flash_message(state: MutableMapping[str, Any], message: str, level: str = "success") -> None:
    if level not in {"success", "warning", "error"}:
        raise ValueError("Flash message level must be success, warning, or error.")
    state["flash_message"] = message
    state["flash_message_level"] = level


def pop_flash_message(state: MutableMapping[str, Any]) -> tuple[str, str] | None:
    message = state.pop("flash_message", None)
    level = state.pop("flash_message_level", None)
    if message is None or level is None:
        return None
    return str(message), str(level)


def contact_form_key(prefix: str, field_name: str) -> str:
    return f"{prefix}_{field_name}"


def initialize_contact_form_state(state: MutableMapping[str, Any], prefix: str, values: Optional[dict[str, Any]] = None) -> None:
    source = {**ADD_CONTACT_DEFAULTS, **(values or {})}
    for field_name, value in source.items():
        state.setdefault(contact_form_key(prefix, field_name), value)


def reset_contact_form_state(state: MutableMapping[str, Any], prefix: str) -> None:
    for field_name, value in ADD_CONTACT_DEFAULTS.items():
        state[contact_form_key(prefix, field_name)] = value


def contact_form_snapshot(state: MutableMapping[str, Any], prefix: str) -> dict[str, Any]:
    initialize_contact_form_state(state, prefix)
    return {field_name: state.get(contact_form_key(prefix, field_name)) for field_name in ADD_CONTACT_DEFAULTS}


def validate_contact_form_state(state: MutableMapping[str, Any], prefix: str) -> tuple[dict[str, Any], dict[str, str]]:
    values = contact_form_snapshot(state, prefix)
    errors: dict[str, str] = {}
    payload = dict(values)
    try:
        payload["first_name"] = normalize_name(values["first_name"], "First name")
        payload["last_name"] = normalize_name(values["last_name"], "Last name")
        validate_contact_identity(payload["first_name"], payload["last_name"], values.get("email"), values.get("phone"))
    except ValueError as exc:
        errors["name"] = str(exc)
    try:
        payload["job_title"] = normalize_contact_title(values["title_selection"], values["other_title"])
    except ValueError:
        errors["title"] = "Enter a title when Other is selected."
    try:
        payload["phone"] = normalize_contact_phone(values["phone"])
    except ValueError as exc:
        errors["phone"] = str(exc)
    try:
        payload["email"] = normalize_email(values["email"])
    except ValueError as exc:
        errors["email"] = str(exc)
    try:
        payload["decision_role"] = validate_decision_role(values["decision_role"])
    except ValueError as exc:
        errors["decision_role"] = str(exc)
    return payload, errors
