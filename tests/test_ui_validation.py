import pytest

from app.constants import (
    COMMISSION_STATUSES,
    CONTACT_TITLES,
    DECISION_ROLES,
    FULFILLMENT_STATUSES,
    INDUSTRIES,
    LEAD_SOURCES,
    LOCATION_TYPES,
    PRODUCT_CATALOG,
    US_STATES,
)
from app.enums import LocationType
from app.validation import (
    clean_optional_text,
    format_us_phone,
    format_phone_display,
    generate_location_label,
    normalize_contact_title,
    normalize_company_phone,
    normalize_contact_phone,
    normalize_email,
    normalize_name,
    normalize_person_name,
    normalize_city,
    normalize_phone,
    normalize_zip_code,
    normalize_website,
    state_display_label,
    title_selection_for_existing,
    validate_decision_role,
    validate_location_type,
    validate_person_name,
    validate_us_phone,
    validate_us_state,
    validate_email,
    validate_state,
    validate_zip,
    validate_company_name,
    validate_contact_identity,
    validate_industry_selection,
    validate_location_fields,
    validate_lead_source,
    validate_referral_partner_identity,
    validate_source_metadata,
)


def test_clean_optional_text_strips_and_normalizes_blank() -> None:
    assert clean_optional_text("  value  ") == "value"
    assert clean_optional_text("   ") is None


def test_validate_company_name_rejects_blank() -> None:
    with pytest.raises(ValueError, match="Company name"):
        validate_company_name(" ")


def test_validate_contact_identity_accepts_any_identity_value() -> None:
    validate_contact_identity("Mary", "", "owner@example.com", "")


def test_validate_contact_identity_rejects_empty_contact() -> None:
    with pytest.raises(ValueError, match="first name or last name"):
        validate_contact_identity("", "", "", "")


def test_contact_email_validation_and_normalization() -> None:
    assert normalize_email("") is None
    assert normalize_email("John.Smith@Company.COM") == "john.smith@company.com"
    assert normalize_email("john+sales@company.co") == "john+sales@company.co"
    assert validate_email(" OWNER@EXAMPLE.COM ") == "owner@example.com"
    assert validate_email(" OWNER@EXAMPLE.COM ", field_name="Referral partner email") == "owner@example.com"


@pytest.mark.parametrize("value", ["some", "john@", "@gmail.com", "john.com", "john @company.com", "john@ company.com", "test@example", "multiple@@company.com"])
def test_invalid_contact_email_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="valid email address"):
        normalize_email(value)


def test_referral_email_error_uses_field_specific_message() -> None:
    with pytest.raises(ValueError, match="valid referral partner email address"):
        validate_email("1.com", field_name="Referral partner email")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("mary", "Mary"),
        ("o'connor", "O'Connor"),
        ("smith-jones", "Smith-Jones"),
        ("  mary   ann  ", "Mary Ann"),
    ],
)
def test_contact_name_normalization(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected
    assert normalize_person_name(raw) == expected
    assert validate_person_name(raw) == expected


def test_contact_title_rules() -> None:
    assert normalize_contact_title("Owner") == "Owner"
    assert normalize_contact_title("Select title") is None
    with pytest.raises(ValueError, match="Other title"):
        normalize_contact_title("Other", "")
    assert normalize_contact_title("Other", "chief scheduler") == "chief scheduler"
    assert title_selection_for_existing("Chief Scheduler") == ("Other", "Chief Scheduler")


@pytest.mark.parametrize("value", ["UNKNOWN", "DECISION_MAKER", "INFLUENCER", "GATEKEEPER"])
def test_decision_role_values_are_accepted(value: str) -> None:
    assert validate_decision_role(value).value == value


def test_unsupported_decision_role_is_rejected() -> None:
    with pytest.raises(ValueError, match="decision role"):
        validate_decision_role("BUYER")


def test_validate_location_fields_requires_company() -> None:
    with pytest.raises(ValueError, match="Company"):
        validate_location_fields(None, "Spring Hill", "FL", "34609")


def test_validate_location_fields_requires_reasonable_zip() -> None:
    with pytest.raises(ValueError, match="ZIP"):
        validate_location_fields(1, "Spring Hill", "FL", "123")


def test_blank_location_label_auto_generates_city_office() -> None:
    assert generate_location_label("", "spring hill") == "Spring Hill Office"


def test_blank_location_label_without_city_generates_main_office() -> None:
    assert generate_location_label("", "") == "Main Office"


def test_custom_location_label_is_preserved() -> None:
    assert generate_location_label("Warehouse 2", "Tampa") == "Warehouse 2"


def test_valid_zip_is_accepted() -> None:
    assert normalize_zip_code("34655") == "34655"
    assert validate_zip("34655") == "34655"


@pytest.mark.parametrize("value", ["3465", "346551", "34A55", "34-655", "ABCDE"])
def test_invalid_zip_values_are_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="ZIP code must contain exactly 5 digits"):
        normalize_zip_code(value)


@pytest.mark.parametrize("state", ["FL", "TX", "DC"])
def test_valid_states_are_accepted(state: str) -> None:
    assert validate_us_state(state) == state
    assert validate_state(state.lower()) == state


def test_invalid_state_is_rejected() -> None:
    with pytest.raises(ValueError, match="Please select a state"):
        validate_us_state("ZZ")


def test_state_display_label() -> None:
    assert state_display_label("FL") == "FL — Florida"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("new port richey", "New Port Richey"),
        ("new   port   richey", "New Port Richey"),
        ("land o lakes", "Land O' Lakes"),
        ("Wesley Chapel", "Wesley Chapel"),
    ],
)
def test_city_normalization(raw: str, expected: str) -> None:
    assert normalize_city(raw) == expected


@pytest.mark.parametrize("value", [LocationType.SMB, LocationType.SOHO, LocationType.BAR_RESTAURANT, "SMB", "SOHO", "B&R"])
def test_valid_location_types_are_accepted(value) -> None:
    assert validate_location_type(value) in {LocationType.SMB, LocationType.SOHO, LocationType.BAR_RESTAURANT}


@pytest.mark.parametrize("value", [LocationType.COMMERCIAL, "WAREHOUSE", None])
def test_invalid_location_type_is_rejected(value) -> None:
    with pytest.raises(ValueError, match="Please select a location type"):
        validate_location_type(value)


def test_validate_source_metadata_requires_pair() -> None:
    with pytest.raises(ValueError, match="provided together"):
        validate_source_metadata("salesforce", None)


def test_validate_source_metadata_normalizes_source_system() -> None:
    assert validate_source_metadata(" Salesforce ", " 001 ") == ("salesforce", "001")


def test_validate_lead_source_allows_only_standard_values() -> None:
    assert validate_lead_source("AE Found") == "AE_FOUND"
    assert validate_lead_source("referral") == "REFERRAL"
    with pytest.raises(ValueError, match="Lead source"):
        validate_lead_source("Trade show")


def test_validate_referral_partner_identity_requires_at_least_one_value() -> None:
    validate_referral_partner_identity("", "", "Local Chamber", "", "")
    with pytest.raises(ValueError, match="referral partner"):
        validate_referral_partner_identity("", "", "", "", "")


def test_blank_optional_phone_is_accepted() -> None:
    assert normalize_company_phone("") is None


def test_valid_ten_digit_phone_is_accepted() -> None:
    assert normalize_company_phone("2321231234") == "2321231234"


def test_phone_with_letters_is_rejected() -> None:
    with pytest.raises(ValueError, match="digits only"):
        normalize_company_phone("232abc1234")


def test_phone_with_unsupported_symbols_is_rejected() -> None:
    with pytest.raises(ValueError, match="digits only"):
        normalize_company_phone("(232)123-1234")


def test_phone_shorter_than_ten_digits_is_rejected() -> None:
    with pytest.raises(ValueError, match="exactly 10"):
        normalize_company_phone("232123123")


def test_phone_longer_than_ten_digits_is_rejected() -> None:
    with pytest.raises(ValueError, match="exactly 10"):
        normalize_company_phone("12321231234")


def test_phone_display_format() -> None:
    assert format_us_phone("2321231234") == "(232) 123-1234"
    assert format_phone_display("2321231234") == "(232) 123-1234"


def test_shared_phone_helper_uses_field_label() -> None:
    assert normalize_phone("2321231234", field_name="Contact phone") == "2321231234"
    with pytest.raises(ValueError, match="Contact phone must contain digits only"):
        validate_us_phone("232abc1234", field_name="Contact phone")


def test_blank_contact_phone_is_accepted() -> None:
    assert normalize_contact_phone("") is None


def test_valid_contact_phone_is_accepted() -> None:
    assert normalize_contact_phone("2321231234") == "2321231234"


@pytest.mark.parametrize("value", ["232abc1234", "232-123-1234", "(232)1231234"])
def test_contact_phone_with_invalid_characters_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="Contact phone must contain digits only"):
        normalize_contact_phone(value)


@pytest.mark.parametrize("value", ["232123123", "12321231234"])
def test_contact_phone_wrong_length_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="Contact phone must contain exactly 10 digits"):
        normalize_contact_phone(value)


def test_industry_selection_required() -> None:
    with pytest.raises(ValueError, match="select an industry"):
        validate_industry_selection("Select industry")


def test_standard_industry_is_accepted() -> None:
    assert validate_industry_selection("Plumbing") == "Plumbing"


def test_other_industry_requires_text() -> None:
    with pytest.raises(ValueError, match="Other industry"):
        validate_industry_selection("Other", "")
    assert validate_industry_selection("Other", "Pet services") == "Pet services"


def test_valid_bare_domain_is_accepted() -> None:
    assert normalize_website("example.com") == "https://example.com"


def test_valid_https_website_is_accepted() -> None:
    assert normalize_website("https://www.example.com/path") == "https://www.example.com/path"


@pytest.mark.parametrize("value", ["example", "http://", ".com", "random text"])
def test_invalid_website_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="valid website"):
        normalize_website(value)


def test_email_entered_as_website_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid website"):
        normalize_website("test@site.com")


def test_controlled_values_are_centralized() -> None:
    assert "FL" in US_STATES
    assert "Plumbing" in INDUSTRIES
    assert "Owner" in CONTACT_TITLES
    assert LocationType.SMB in LOCATION_TYPES
    assert LocationType.SOHO in LOCATION_TYPES
    assert LocationType.BAR_RESTAURANT in LOCATION_TYPES
    assert {"AE_FOUND", "REFERRAL"} <= set(LEAD_SOURCES)
    assert any(role.value == "DECISION_MAKER" for role in DECISION_ROLES)


def test_product_catalog_and_commission_status_constants_are_centralized() -> None:
    assert PRODUCT_CATALOG == (
        "Internet",
        "Mobile",
        "Voice",
        "TV",
        "Seasonal Sports",
        "EverPass",
        "Managed WiFi",
        "Security",
        "Other",
    )
    assert COMMISSION_STATUSES == (
        "Pending Fulfillment",
        "Commission Eligible",
        "Commission Paid",
    )
    assert FULFILLMENT_STATUSES == (
        "Pending",
        "Installed",
        "Activated",
        "Cancelled",
    )
