from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect

from app.crud import (
    DuplicateRecordError,
    ValidationError,
    archive_company,
    assign_referral_partner,
    create_company,
    create_contact,
    create_location,
    create_referral_partner,
    deactivate_contact,
    deactivate_location,
    deactivate_referral_partner,
    get_company,
    list_companies,
    list_company_contacts,
    list_company_locations,
    list_referral_partners,
    remove_or_change_referral_partner,
    restore_company,
    restore_contact,
    restore_location,
    restore_referral_partner,
    update_company,
)
from app.enums import ActivityType, ContactRole, LocationType
from app.models import Activity, Company, Contact, Location, ReferralPartner
from app.validation import LEAD_SOURCE_AE_FOUND, LEAD_SOURCE_REFERRAL


def test_company_archive_preserves_children_and_filters_by_default(db_session) -> None:
    company = create_company(db_session, name="Archive Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="10 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.SMB,
    )
    contact = create_contact(db_session, company_id=company.id, first_name="Alex")

    archive_company(db_session, company.id)

    assert list_companies(db_session) == ()
    assert list_companies(db_session, include_archived=True)[0].is_active is False
    assert db_session.get(Location, location.id) is not None
    assert db_session.get(Contact, contact.id) is not None

    restore_company(db_session, company.id)
    assert list_companies(db_session)[0].name == "Archive Co"


def test_contact_deactivate_and_restore_preserves_relationships(db_session) -> None:
    company = create_company(db_session, name="Contact Status Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Taylor")

    inactive = deactivate_contact(db_session, contact.id, "No longer with company")

    assert inactive.is_active is False
    assert list_company_contacts(db_session, company.id) == ()
    assert list_company_contacts(db_session, company.id, include_inactive=True)[0].company_id == company.id

    restored = restore_contact(db_session, contact.id)
    assert restored.is_active is True
    assert restored.inactive_reason is None


def test_location_deactivate_and_restore_preserves_relationships(db_session) -> None:
    company = create_company(db_session, name="Location Status Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="20 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.SMB,
    )

    inactive = deactivate_location(db_session, location.id, "Closed")

    assert inactive.is_active is False
    assert list_company_locations(db_session, company.id) == ()
    assert list_company_locations(db_session, company.id, include_inactive=True)[0].inactive_reason == "Closed"

    restored = restore_location(db_session, location.id)
    assert restored.is_active is True
    assert restored.inactive_at is None


def test_lead_source_normalizes_to_allowed_values(db_session) -> None:
    ae = create_company(db_session, name="AE Found Co", lead_source="AE Found")
    referral_partner = create_referral_partner(db_session, organization="Chamber of Commerce")
    referral = create_company(
        db_session,
        name="Referral Co",
        lead_source="referral",
        referral_partner_id=referral_partner.id,
    )

    assert ae.lead_source == LEAD_SOURCE_AE_FOUND
    assert referral.lead_source == LEAD_SOURCE_REFERRAL


def test_invalid_lead_source_is_rejected(db_session) -> None:
    with pytest.raises(ValidationError, match="Lead source"):
        create_company(db_session, name="Bad Lead Source Co", lead_source="Door knock")


def test_referral_company_requires_partner(db_session) -> None:
    with pytest.raises(ValidationError, match="Referral companies require"):
        create_company(db_session, name="Missing Partner Co", lead_source=LEAD_SOURCE_REFERRAL)


def test_ae_found_company_does_not_require_partner(db_session) -> None:
    company = create_company(db_session, name="Self Sourced Co", lead_source=LEAD_SOURCE_AE_FOUND)

    assert company.referral_partner_id is None


def test_referral_partner_requires_identity(db_session) -> None:
    with pytest.raises(ValidationError, match="At least one referral partner"):
        create_referral_partner(db_session)


def test_referral_partner_source_pair_must_be_complete(db_session) -> None:
    with pytest.raises(ValidationError, match="provided together"):
        create_referral_partner(db_session, organization="Bad Source", source_system="partner_portal")


def test_referral_partner_duplicate_source_pair_is_rejected(db_session) -> None:
    create_referral_partner(db_session, organization="One", source_system="partner_portal", external_id="p-1")

    with pytest.raises(DuplicateRecordError, match="already exists"):
        create_referral_partner(db_session, organization="Two", source_system="partner_portal", external_id="p-1")


def test_referral_partner_can_refer_many_companies(db_session) -> None:
    partner = create_referral_partner(db_session, first_name="Jordan", organization="Local BNI")
    first = create_company(db_session, name="Referral One", lead_source=LEAD_SOURCE_REFERRAL, referral_partner_id=partner.id)
    second = create_company(db_session, name="Referral Two", lead_source=LEAD_SOURCE_REFERRAL, referral_partner_id=partner.id)

    assert get_company(db_session, first.id).referral_partner_name == "Jordan (Local BNI)"
    assert get_company(db_session, second.id).referral_partner_id == partner.id


def test_assign_and_clear_referral_partner_requires_confirmation(db_session) -> None:
    company = create_company(db_session, name="Change Referral Co", lead_source=LEAD_SOURCE_AE_FOUND)
    partner = create_referral_partner(db_session, organization="Referral Group")

    assigned = assign_referral_partner(db_session, company.id, partner.id)
    assert assigned.lead_source == LEAD_SOURCE_REFERRAL

    with pytest.raises(ValidationError, match="Confirm clearing"):
        remove_or_change_referral_partner(db_session, company.id, new_lead_source=LEAD_SOURCE_AE_FOUND)

    cleared = remove_or_change_referral_partner(
        db_session,
        company.id,
        new_lead_source=LEAD_SOURCE_AE_FOUND,
        confirm_clear=True,
    )
    assert cleared.referral_partner_id is None
    assert cleared.lead_source == LEAD_SOURCE_AE_FOUND


def test_referral_partner_deactivate_and_restore(db_session) -> None:
    partner = create_referral_partner(db_session, organization="Inactive Partner")

    deactivate_referral_partner(db_session, partner.id)

    assert list_referral_partners(db_session) == ()
    assert list_referral_partners(db_session, include_inactive=True)[0].is_active is False

    restored = restore_referral_partner(db_session, partner.id)
    assert restored.is_active is True


def test_referral_partner_model_has_no_compensation_fields() -> None:
    columns = set(inspect(ReferralPartner).columns.keys())

    assert not {"cash", "payment", "compensation", "lunch_expense"} & columns


def test_activity_can_reference_referral_partner(db_session) -> None:
    partner = create_referral_partner(db_session, organization="Referral Org")
    company = Company(name="Referral Activity Co", lead_source=LEAD_SOURCE_REFERRAL, referral_partner_id=partner.id)
    db_session.add(company)
    db_session.flush()
    activity = Activity(
        company=company,
        referral_partner_id=partner.id,
        activity_type=ActivityType.DOOR_KNOCK,
        activity_at=datetime.now(UTC),
    )
    db_session.add(activity)
    db_session.commit()

    saved = db_session.get(Activity, activity.id)
    assert saved is not None
    assert saved.referral_partner.organization == "Referral Org"
    assert db_session.get(ReferralPartner, partner.id).activities[0].id == saved.id


def test_archive_defaults_are_active_on_new_records(db_session) -> None:
    company = create_company(db_session, name="Defaults Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="30 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.SMB,
    )
    contact = create_contact(db_session, company_id=company.id, first_name="Casey", decision_role=ContactRole.UNKNOWN)

    assert company.is_active is True
    assert location.is_active is True
    assert contact.is_active is True


def test_update_company_referral_validation(db_session) -> None:
    company = create_company(db_session, name="Update Referral Co", lead_source=LEAD_SOURCE_AE_FOUND)
    partner = create_referral_partner(db_session, organization="Update Partner")

    with pytest.raises(ValidationError, match="can only be assigned"):
        update_company(db_session, company.id, lead_source=LEAD_SOURCE_AE_FOUND, referral_partner_id=partner.id)
