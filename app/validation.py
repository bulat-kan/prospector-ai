import re
from urllib.parse import urlparse
from typing import Optional

from app.constants import (
    CONTACT_TITLE_OPTIONS,
    CONTACT_TITLE_OTHER,
    CONTACT_TITLE_PLACEHOLDER,
    INDUSTRIES,
    INDUSTRY_OPTIONS,
    INDUSTRY_OTHER,
    INDUSTRY_PLACEHOLDER,
    LEAD_SOURCE_AE_FOUND,
    LEAD_SOURCE_ALIASES,
    LEAD_SOURCE_LABELS,
    LEAD_SOURCE_REFERRAL,
    LOCATION_TYPE_OPTIONS,
    PHONE_DIGIT_LENGTH,
    US_STATES,
)
from app.enums import ContactRole, LocationType


DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?!-)([A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}(/.*)?$"
)
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
STATE_OPTIONS = tuple(US_STATES.keys())


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


def validate_us_phone(value: Optional[str], field_name: str = "Phone") -> Optional[str]:
    cleaned = clean_optional_text(value)
    if cleaned is None:
        return None
    if not cleaned.isdigit():
        raise ValueError(f"{field_name} must contain digits only.")
    if len(cleaned) != PHONE_DIGIT_LENGTH:
        raise ValueError(f"{field_name} must contain exactly {PHONE_DIGIT_LENGTH} digits.")
    return cleaned


def normalize_phone(value: Optional[str], field_name: str = "Phone") -> Optional[str]:
    return validate_us_phone(value, field_name=field_name)


def normalize_company_phone(value: Optional[str]) -> Optional[str]:
    return validate_us_phone(value, field_name="Public phone")


def normalize_contact_phone(value: Optional[str]) -> Optional[str]:
    return validate_us_phone(value, field_name="Contact phone")


def format_phone_display(value: Optional[str]) -> str:
    cleaned = clean_optional_text(value)
    if cleaned is None:
        return ""
    if len(cleaned) == PHONE_DIGIT_LENGTH and cleaned.isdigit():
        return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
    return cleaned


def format_us_phone(value: Optional[str]) -> str:
    return format_phone_display(value)


def normalize_website(value: Optional[str]) -> Optional[str]:
    cleaned = clean_optional_text(value)
    if cleaned is None:
        return None
    if "@" in cleaned or any(character.isspace() for character in cleaned):
        raise ValueError("Enter a valid website, such as example.com or https://example.com.")
    candidate = cleaned if cleaned.startswith(("http://", "https://")) else f"https://{cleaned}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid website, such as example.com or https://example.com.")
    if parsed.netloc in {"", ".com"} or parsed.netloc.startswith(".") or "." not in parsed.netloc:
        raise ValueError("Enter a valid website, such as example.com or https://example.com.")
    domain_with_path = parsed.netloc + (parsed.path if parsed.path and parsed.path != "/" else "")
    if not DOMAIN_PATTERN.match(domain_with_path):
        raise ValueError("Enter a valid website, such as example.com or https://example.com.")
    path = parsed.path if parsed.path and parsed.path != "/" else ""
    return f"https://{parsed.netloc.lower()}{path}"


def validate_industry_selection(industry: Optional[str], other_industry: Optional[str] = None) -> str:
    cleaned = clean_optional_text(industry)
    if cleaned is None or cleaned == INDUSTRY_PLACEHOLDER:
        raise ValueError("Please select an industry.")
    if cleaned == INDUSTRY_OTHER:
        return require_text(other_industry, "Other industry")
    if cleaned not in INDUSTRY_OPTIONS:
        raise ValueError("Please select an industry.")
    return cleaned


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
    if not any(clean_optional_text(value) for value in (first_name, last_name)):
        raise ValueError("Enter at least a first name or last name.")


def normalize_name(value: Optional[str], field_name: str = "Name") -> Optional[str]:
    cleaned = clean_optional_text(value)
    if cleaned is None:
        return None
    collapsed = re.sub(r"\s+", " ", cleaned)

    def normalize_piece(piece: str) -> str:
        return piece[:1].upper() + piece[1:].lower() if piece else piece

    words = []
    for word in collapsed.split(" "):
        hyphen_parts = []
        for hyphen_part in word.split("-"):
            apostrophe_parts = [normalize_piece(part) for part in hyphen_part.split("'")]
            hyphen_parts.append("'".join(apostrophe_parts))
        words.append("-".join(hyphen_parts))
    return " ".join(words)


def normalize_person_name(value: Optional[str], field_name: str = "Name") -> Optional[str]:
    return normalize_name(value, field_name=field_name)


def validate_person_name(value: Optional[str], field_name: str = "Name") -> Optional[str]:
    return normalize_person_name(value, field_name=field_name)


def contact_display_name(first_name: Optional[str], last_name: Optional[str]) -> str:
    full_name = " ".join(value for value in (clean_optional_text(first_name), clean_optional_text(last_name)) if value)
    return full_name or "Contact"


def _email_error_message(field_name: str) -> str:
    if field_name == "Email":
        return "Enter a valid email address, such as name@company.com."
    return f"Enter a valid {field_name.lower()} address, such as name@company.com."


def normalize_email(value: Optional[str], field_name: str = "Email") -> Optional[str]:
    cleaned = clean_optional_text(value)
    if cleaned is None:
        return None
    normalized = cleaned.lower()
    if any(character.isspace() for character in normalized) or normalized.count("@") != 1:
        raise ValueError(_email_error_message(field_name))
    local_part, domain = normalized.split("@")
    if not local_part or not domain or not EMAIL_PATTERN.match(normalized):
        raise ValueError(_email_error_message(field_name))
    return normalized


def validate_email(value: Optional[str], field_name: str = "Email") -> Optional[str]:
    return normalize_email(value, field_name=field_name)


def validate_decision_role(value: ContactRole | str | None) -> ContactRole:
    if value is None:
        raise ValueError("Please select a decision role.")
    try:
        return value if isinstance(value, ContactRole) else ContactRole(str(value))
    except ValueError as exc:
        raise ValueError("Please select a decision role.") from exc


def normalize_contact_title(title: Optional[str], other_title: Optional[str] = None) -> Optional[str]:
    cleaned = clean_optional_text(title)
    if cleaned is None or cleaned == CONTACT_TITLE_PLACEHOLDER:
        return None
    if cleaned == CONTACT_TITLE_OTHER:
        return require_text(other_title, "Other title")
    if cleaned not in CONTACT_TITLE_OPTIONS:
        return normalize_name(cleaned, "Title")
    return cleaned


def title_selection_for_existing(value: Optional[str]) -> tuple[str, str]:
    cleaned = clean_optional_text(value)
    if cleaned is None:
        return CONTACT_TITLE_PLACEHOLDER, ""
    if cleaned in CONTACT_TITLE_OPTIONS and cleaned != CONTACT_TITLE_OTHER:
        return cleaned, ""
    return CONTACT_TITLE_OTHER, cleaned


def validate_location_fields(company_id: Optional[int], city: Optional[str], state: Optional[str], postal_code: Optional[str]) -> None:
    if company_id is None:
        raise ValueError("Company is required.")
    normalize_city(city)
    validate_us_state(state)
    normalize_zip_code(postal_code)


def normalize_zip_code(value: Optional[str]) -> str:
    cleaned = require_text(value, "ZIP code")
    if not cleaned.isdigit() or len(cleaned) != 5:
        raise ValueError("ZIP code must contain exactly 5 digits.")
    return cleaned


def validate_zip(value: Optional[str]) -> str:
    return normalize_zip_code(value)


def validate_us_state(value: Optional[str]) -> str:
    cleaned = require_text(value, "State").upper()
    if cleaned not in US_STATES:
        raise ValueError("Please select a state.")
    return cleaned


def validate_state(value: Optional[str]) -> str:
    return validate_us_state(value)


def normalize_city(value: Optional[str]) -> str:
    cleaned = require_text(value, "City")
    collapsed = re.sub(r"\s+", " ", cleaned)
    normalized_words = []
    for word in collapsed.split(" "):
        pieces = word.split("'")
        normalized_words.append("'".join(piece[:1].upper() + piece[1:].lower() if piece else piece for piece in pieces))
    normalized = " ".join(normalized_words)
    if normalized.lower() == "land o lakes":
        return "Land O' Lakes"
    return normalized


def normalize_street_address(value: Optional[str]) -> str:
    return require_text(value, "Street address")


def validate_location_type(value: LocationType | str | None) -> LocationType:
    if value is None:
        raise ValueError("Please select a location type.")
    try:
        location_type = value if isinstance(value, LocationType) else LocationType(str(value))
    except ValueError as exc:
        raise ValueError("Please select a location type.") from exc
    if location_type not in LOCATION_TYPE_OPTIONS:
        raise ValueError("Please select a location type.")
    return location_type


def generate_location_label(location_name: Optional[str], city: Optional[str]) -> str:
    custom_label = clean_optional_text(location_name)
    if custom_label is not None:
        return custom_label
    try:
        normalized_city = normalize_city(city)
    except ValueError:
        return "Main Office"
    return f"{normalized_city} Office"


def state_display_label(abbreviation: str) -> str:
    return f"{abbreviation} — {US_STATES[abbreviation]}"


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
