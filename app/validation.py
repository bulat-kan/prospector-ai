from typing import Optional


LEAD_SOURCE_AE_FOUND = "AE_FOUND"
LEAD_SOURCE_REFERRAL = "REFERRAL"
LEAD_SOURCE_LABELS = {
    LEAD_SOURCE_AE_FOUND: "AE Found",
    LEAD_SOURCE_REFERRAL: "Referral",
}
LEAD_SOURCE_ALIASES = {
    "ae found": LEAD_SOURCE_AE_FOUND,
    "ae_found": LEAD_SOURCE_AE_FOUND,
    "aefound": LEAD_SOURCE_AE_FOUND,
    "referral": LEAD_SOURCE_REFERRAL,
}


def clean_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def require_text(value: Optional[str], field_name: str) -> str:
    cleaned = clean_optional_text(value)
    if cleaned is None:
        raise ValueError(f"{field_name} is required.")
    return cleaned


def validate_company_name(name: Optional[str]) -> str:
    return require_text(name, "Company name")


def validate_lead_source(value: Optional[str]) -> Optional[str]:
    cleaned = clean_optional_text(value)
    if cleaned is None:
        return None
    normalized = LEAD_SOURCE_ALIASES.get(cleaned.strip().lower().replace("-", " "))
    if normalized is None and cleaned in LEAD_SOURCE_LABELS:
        normalized = cleaned
    if normalized is None:
        raise ValueError("Lead source must be AE Found or Referral.")
    return normalized


def validate_contact_identity(
    first_name: Optional[str],
    last_name: Optional[str],
    email: Optional[str],
    phone: Optional[str],
) -> None:
    if not any(clean_optional_text(value) for value in (first_name, last_name, email, phone)):
        raise ValueError("At least one contact name, email, or phone value is required.")


def validate_location_fields(company_id: Optional[int], city: Optional[str], state: Optional[str], postal_code: Optional[str]) -> None:
    if company_id is None:
        raise ValueError("Company is required.")
    require_text(city, "City")
    cleaned_state = require_text(state, "State")
    if len(cleaned_state) < 2:
        raise ValueError("State must be at least 2 characters.")
    cleaned_postal_code = require_text(postal_code, "ZIP code")
    if len(cleaned_postal_code) < 5:
        raise ValueError("ZIP code must be at least 5 characters.")


def validate_source_metadata(
    source_system: Optional[str],
    external_id: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    cleaned_source = clean_optional_text(source_system)
    cleaned_external_id = clean_optional_text(external_id)
    if bool(cleaned_source) != bool(cleaned_external_id):
        raise ValueError("source_system and external_id must be provided together.")
    if cleaned_source is None:
        return None, None
    return cleaned_source.lower(), cleaned_external_id


def validate_referral_partner_identity(
    first_name: Optional[str],
    last_name: Optional[str],
    organization: Optional[str],
    phone: Optional[str],
    email: Optional[str],
) -> None:
    if not any(clean_optional_text(value) for value in (first_name, last_name, organization, phone, email)):
        raise ValueError("At least one referral partner name, organization, email, or phone value is required.")
