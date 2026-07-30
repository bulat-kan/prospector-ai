import pytest

from app.validation import (
    clean_optional_text,
    validate_company_name,
    validate_contact_identity,
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
    validate_contact_identity("", "", "owner@example.com", "")


def test_validate_contact_identity_rejects_empty_contact() -> None:
    with pytest.raises(ValueError, match="At least one"):
        validate_contact_identity("", "", "", "")


def test_validate_location_fields_requires_company() -> None:
    with pytest.raises(ValueError, match="Company"):
        validate_location_fields(None, "Spring Hill", "FL", "34609")


def test_validate_location_fields_requires_reasonable_zip() -> None:
    with pytest.raises(ValueError, match="ZIP"):
        validate_location_fields(1, "Spring Hill", "FL", "123")


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
