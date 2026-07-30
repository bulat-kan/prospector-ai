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
    company = create_company(db_session, name="North Coast Roofing", main_phone="555-0100")

    assert company.id > 0
    assert company.name == "North Coast Roofing"
    assert company.main_phone == "555-0100"


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


def test_add_location_to_company(db_session) -> None:
    company = create_company(db_session, name="Location Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="10 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.COMMERCIAL,
    )

    assert location.company_id == company.id
    assert list_company_locations(db_session, company.id)[0].id == location.id


def test_add_commercial_location(db_session) -> None:
    company = create_company(db_session, name="Commercial Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="20 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.COMMERCIAL,
    )

    assert location.location_type == LocationType.COMMERCIAL


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
        location_type=LocationType.RESIDENTIAL,
    )

    assert {soho.location_type, residential.location_type} == {LocationType.SOHO, LocationType.RESIDENTIAL}


def test_update_location(db_session) -> None:
    company = create_company(db_session, name="Update Location Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="40 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.COMMERCIAL,
    )

    updated = update_location(db_session, location.id, city="Tampa", postal_code="33602")

    assert updated.city == "Tampa"
    assert updated.postal_code == "33602"


def test_add_contact(db_session) -> None:
    company = create_company(db_session, name="Contact Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Jane", last_name="Owner")

    assert contact.company_id == company.id
    assert contact.first_name == "Jane"


def test_reject_empty_contact(db_session) -> None:
    company = create_company(db_session, name="Empty Contact Co")

    with pytest.raises(ValidationError, match="At least one"):
        create_contact(db_session, company_id=company.id)


def test_update_contact(db_session) -> None:
    company = create_company(db_session, name="Update Contact Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Jane")

    updated = update_contact(
        db_session,
        contact.id,
        first_name="Janet",
        email="janet@example.com",
        decision_role=ContactRole.DECISION_MAKER,
        is_primary_contact=True,
    )

    assert updated.first_name == "Janet"
    assert updated.email == "janet@example.com"
    assert updated.decision_role == ContactRole.DECISION_MAKER
    assert updated.is_primary_contact is True


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
        location_type=LocationType.COMMERCIAL,
    )
    with pytest.raises(CrudError):
        create_location(
            db_session,
            company_id=company.id,
            address_line_1="50 Main St",
            city="Spring Hill",
            state="FL",
            postal_code="34609",
            location_type=LocationType.COMMERCIAL,
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
