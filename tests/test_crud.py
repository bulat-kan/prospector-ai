from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.crud import (
    CrudError,
    DuplicateRecordError,
    RecordNotFoundError,
    ValidationError,
    create_company,
    create_contact,
    create_location,
    get_company,
    get_contact,
    get_location,
    list_companies,
    list_company_contacts,
    list_company_locations,
    update_company,
    update_contact,
    update_location,
)
from app.enums import ContactRole, LocationType
from app.models import CommissionPlan, CommissionTier
from app.seed_demo import COMMISSION_PLAN_NAME, COMMISSION_TIER_PRESENTATION, seed_configuration, seed_demo


def test_create_company(db_session) -> None:
    company = create_company(db_session, name="North Coast Roofing", main_phone="7275550100")

    assert company.id > 0
    assert company.name == "North Coast Roofing"
    assert company.main_phone == "7275550100"


def test_reject_blank_company_name(db_session) -> None:
    with pytest.raises(ValidationError, match="Company name"):
        create_company(db_session, name="   ")


def test_duplicate_company_behavior(db_session) -> None:
    create_company(db_session, name="Duplicate Co")

    with pytest.raises(DuplicateRecordError, match="already exists"):
        create_company(db_session, name="duplicate co")


def test_create_company_with_salesforce_source_metadata(db_session) -> None:
    imported_at = datetime.now(UTC)
    company = create_company(
        db_session,
        name="Imported Co",
        source_system="Salesforce",
        external_id="001xx000003DGbY",
        last_imported_at=imported_at,
    )

    assert company.source_system == "salesforce"
    assert company.external_id == "001xx000003DGbY"


def test_reject_source_system_without_external_id(db_session) -> None:
    with pytest.raises(ValidationError, match="provided together"):
        create_company(db_session, name="Bad Source", source_system="salesforce")


def test_reject_external_id_without_source_system(db_session) -> None:
    with pytest.raises(ValidationError, match="provided together"):
        create_company(db_session, name="Bad External", external_id="001")


def test_reject_duplicate_source_system_external_id(db_session) -> None:
    create_company(db_session, name="Imported One", source_system="salesforce", external_id="001")

    with pytest.raises(DuplicateRecordError, match="already exists"):
        create_company(db_session, name="Imported Two", source_system="salesforce", external_id="001")


def test_company_phone_is_normalized_and_invalid_phone_rejected(db_session) -> None:
    company = create_company(db_session, name="Phone Co", main_phone="2321231234")

    assert company.main_phone == "2321231234"
    with pytest.raises(ValidationError, match="digits only"):
        create_company(db_session, name="Bad Phone Co", main_phone="232abc1234")


def test_company_website_is_normalized_and_invalid_website_rejected(db_session) -> None:
    company = create_company(db_session, name="Website Co", website="example.com")

    assert company.website == "https://example.com"
    with pytest.raises(ValidationError, match="valid website"):
        create_company(db_session, name="Bad Website Co", website="test@site.com")


def test_failed_referral_validation_does_not_create_company(db_session) -> None:
    with pytest.raises(ValidationError, match="Referral companies require"):
        create_company(db_session, name="No Partial Referral Co", lead_source="Referral")

    assert list_companies(db_session, search="No Partial Referral") == ()


def test_add_location_to_company(db_session) -> None:
    company = create_company(db_session, name="Location Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="10 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.SMB,
    )

    assert location.company_id == company.id
    assert list_company_locations(db_session, company.id)[0].id == location.id
    assert location.location_name == "Spring Hill Office"


def test_add_commercial_location(db_session) -> None:
    company = create_company(db_session, name="Commercial Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="20 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.SMB,
    )

    assert location.location_type == LocationType.SMB


def test_add_soho_residential_location(db_session) -> None:
    company = create_company(db_session, name="SOHO Co")
    soho = create_location(
        db_session,
        company_id=company.id,
        address_line_1="30 Home St",
        city="Spring Hill",
        state="FL",
        postal_code="34608",
        location_type=LocationType.SOHO,
    )
    residential = create_location(
        db_session,
        company_id=company.id,
        address_line_1="31 Home St",
        city="Spring Hill",
        state="FL",
        postal_code="34608",
        location_type=LocationType.SOHO,
    )

    assert {soho.location_type, residential.location_type} == {LocationType.SOHO}


def test_update_location(db_session) -> None:
    company = create_company(db_session, name="Update Location Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="40 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.SMB,
    )

    updated = update_location(db_session, location.id, city="Tampa", postal_code="33602")

    assert updated.city == "Tampa"
    assert updated.postal_code == "33602"


def test_location_crud_normalizes_city_and_generates_label(db_session) -> None:
    company = create_company(db_session, name="Location Quality Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="40 Main St",
        city="land o lakes",
        state="fl",
        postal_code="34639",
        location_type=LocationType.SMB,
    )

    assert location.city == "Land O' Lakes"
    assert location.state == "FL"
    assert location.location_name == "Land O' Lakes Office"


def test_location_custom_label_remains_unchanged(db_session) -> None:
    company = create_company(db_session, name="Custom Label Co")
    location = create_location(
        db_session,
        company_id=company.id,
        location_name="Yard",
        address_line_1="45 Main St",
        city="tampa",
        state="FL",
        postal_code="33602",
        location_type=LocationType.SMB,
    )

    assert location.location_name == "Yard"


@pytest.mark.parametrize("postal_code", ["3465", "346551", "34A55", "34-655"])
def test_location_crud_rejects_invalid_zip(db_session, postal_code: str) -> None:
    company = create_company(db_session, name=f"Invalid ZIP {postal_code}")

    with pytest.raises(ValidationError, match="ZIP code must contain exactly 5 digits"):
        create_location(
            db_session,
            company_id=company.id,
            address_line_1="50 Main St",
            city="Tampa",
            state="FL",
            postal_code=postal_code,
            location_type=LocationType.SMB,
        )


def test_location_crud_rejects_invalid_state(db_session) -> None:
    company = create_company(db_session, name="Invalid State Co")

    with pytest.raises(ValidationError, match="Please select a state"):
        create_location(
            db_session,
            company_id=company.id,
            address_line_1="60 Main St",
            city="Tampa",
            state="ZZ",
            postal_code="33602",
            location_type=LocationType.SMB,
        )


def test_location_crud_rejects_invalid_location_type(db_session) -> None:
    company = create_company(db_session, name="Invalid Type Co")

    with pytest.raises(ValidationError, match="Please select a location type"):
        create_location(
            db_session,
            company_id=company.id,
            address_line_1="70 Main St",
            city="Tampa",
            state="FL",
            postal_code="33602",
            location_type=LocationType.COMMERCIAL,
        )


def test_add_contact(db_session) -> None:
    company = create_company(db_session, name="Contact Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Jane", last_name="Owner", phone="2321231234")

    assert contact.company_id == company.id
    assert contact.first_name == "Jane"
    assert contact.phone == "2321231234"


def test_reject_empty_contact(db_session) -> None:
    company = create_company(db_session, name="Empty Contact Co")

    with pytest.raises(ValidationError, match="first name or last name"):
        create_contact(db_session, company_id=company.id)


def test_update_contact(db_session) -> None:
    company = create_company(db_session, name="Update Contact Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Jane")

    updated = update_contact(
        db_session,
        contact.id,
        first_name="Janet",
        email="janet@example.com",
        phone="2321231234",
        decision_role=ContactRole.DECISION_MAKER,
        is_primary_contact=True,
    )

    assert updated.first_name == "Janet"
    assert updated.email == "janet@example.com"
    assert updated.phone == "2321231234"
    assert updated.decision_role == ContactRole.DECISION_MAKER
    assert updated.is_primary_contact is True


def test_create_contact_accepts_blank_phone(db_session) -> None:
    company = create_company(db_session, name="Blank Contact Phone Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Blank", phone="")

    assert contact.phone is None


def test_create_contact_rejects_invalid_phone(db_session) -> None:
    company = create_company(db_session, name="Bad Contact Phone Co")

    with pytest.raises(ValidationError, match="Contact phone must contain digits only"):
        create_contact(db_session, company_id=company.id, first_name="Bad", phone="abc")

    assert list_company_contacts(db_session, company.id) == ()


def test_update_contact_rejects_invalid_phone_and_rolls_back(db_session) -> None:
    company = create_company(db_session, name="Update Bad Contact Phone Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Good", phone="2321231234")

    with pytest.raises(ValidationError, match="Contact phone must contain digits only"):
        update_contact(db_session, contact.id, phone="232-123-1234")

    assert get_contact(db_session, contact.id).phone == "2321231234"


def test_contact_email_normalizes_and_invalid_email_rejected(db_session) -> None:
    company = create_company(db_session, name="Email Contact Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Mary", email="Mary@Company.COM")

    assert contact.email == "mary@company.com"
    with pytest.raises(ValidationError, match="valid email address"):
        create_contact(db_session, company_id=company.id, first_name="Bad", email="some")


def test_update_contact_rejects_invalid_email_and_rolls_back(db_session) -> None:
    company = create_company(db_session, name="Update Email Contact Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Mary", email="mary@company.com")

    with pytest.raises(ValidationError, match="valid email address"):
        update_contact(db_session, contact.id, email="multiple@@company.com")

    assert get_contact(db_session, contact.id).email == "mary@company.com"


def test_contact_name_rules_and_normalization(db_session) -> None:
    company = create_company(db_session, name="Name Contact Co")
    first_only = create_contact(db_session, company_id=company.id, first_name="mary")
    last_only = create_contact(db_session, company_id=company.id, last_name="o'connor")
    both = create_contact(db_session, company_id=company.id, first_name="mary-ann", last_name="smith-jones")

    assert first_only.first_name == "Mary"
    assert last_only.last_name == "O'Connor"
    assert both.first_name == "Mary-Ann"
    assert both.last_name == "Smith-Jones"


def test_contact_title_and_decision_role_rules(db_session) -> None:
    company = create_company(db_session, name="Title Contact Co")
    contact = create_contact(
        db_session,
        company_id=company.id,
        first_name="Mary",
        job_title="Owner",
        decision_role=ContactRole.INFLUENCER,
        is_primary_contact=True,
    )

    assert contact.job_title == "Owner"
    assert contact.decision_role == ContactRole.INFLUENCER
    assert contact.is_primary_contact is True

    updated = update_contact(db_session, contact.id, job_title="custom title", decision_role=ContactRole.GATEKEEPER)
    assert updated.job_title == "Custom Title"
    assert updated.decision_role == ContactRole.GATEKEEPER
    assert updated.is_primary_contact is True


def test_contact_assigned_location_rules(db_session) -> None:
    company = create_company(db_session, name="Assigned Location Contact Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="1 Main St",
        city="Tampa",
        state="FL",
        postal_code="33602",
        location_type=LocationType.SMB,
    )
    unassigned = create_contact(db_session, company_id=company.id, first_name="Una")
    assigned = create_contact(db_session, company_id=company.id, first_name="Assign", location_id=location.id)

    assert unassigned.location_id is None
    assert assigned.location_id == location.id


def test_missing_company_raises_record_not_found(db_session) -> None:
    with pytest.raises(RecordNotFoundError):
        get_company(db_session, 999)


def test_missing_location_raises_record_not_found(db_session) -> None:
    with pytest.raises(RecordNotFoundError):
        get_location(db_session, 999)


def test_missing_contact_raises_record_not_found(db_session) -> None:
    with pytest.raises(RecordNotFoundError):
        get_contact(db_session, 999)


def test_crud_rollback_works_after_database_failure(db_session) -> None:
    company = create_company(db_session, name="Rollback Co")
    create_location(
        db_session,
        company_id=company.id,
        address_line_1="50 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.SMB,
    )
    with pytest.raises(CrudError):
        create_location(
            db_session,
            company_id=company.id,
            address_line_1="50 Main St",
            city="Spring Hill",
            state="FL",
            postal_code="34609",
            location_type=LocationType.SMB,
        )

    recovered = create_company(db_session, name="After Rollback Co")
    assert recovered.name == "After Rollback Co"


def test_existing_july_2026_seed_data_remains_browseable(db_session) -> None:
    seed_configuration(db_session)
    seed_demo(db_session)

    companies = list_companies(db_session, search="Sunshine")

    assert len(companies) == 1
    assert companies[0].name == "Sunshine Plumbing LLC"
    assert companies[0].location_count >= 2
    assert companies[0].contact_count >= 1


def test_commission_tiers_retain_official_ranges(db_session) -> None:
    seed_configuration(db_session)
    plan = db_session.scalar(select(CommissionPlan).where(CommissionPlan.name == COMMISSION_PLAN_NAME))
    assert plan is not None

    ranges = [(tier.tier_name, tier.minimum_internet, tier.maximum_internet) for tier in plan.tiers]

    assert ranges == [
        ("5-9", 5, 9),
        ("10-14", 10, 14),
        ("15-19", 15, 19),
        ("20-24", 20, 24),
        ("25-29", 25, 29),
        ("30+", 30, None),
    ]


def test_commission_tiers_contain_display_names_and_icons(db_session) -> None:
    seed_configuration(db_session)
    tiers = db_session.scalars(select(CommissionTier)).all()

    assert {tier.tier_name: (tier.display_name, tier.display_icon) for tier in tiers} == COMMISSION_TIER_PRESENTATION


def test_seed_remains_idempotent(db_session) -> None:
    first = seed_configuration(db_session)
    second = seed_configuration(db_session)

    assert first == (7, True, 6)
    assert second == (0, False, 0)
