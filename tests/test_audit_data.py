from sqlalchemy import text

from app.audit_data import audit_companies, audit_contacts, audit_locations
from app.crud import create_company, create_contact, create_location
from app.enums import LocationType


def issue_messages(issues):
    return [issue.message for issue in issues]


def test_audit_reports_zero_issues_for_clean_data(db_session) -> None:
    company = create_company(db_session, name="Clean Audit Co", main_phone="2321231234", website="example.com")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="1 Main St",
        city="Tampa",
        state="FL",
        postal_code="33602",
        location_type=LocationType.SMB,
    )
    create_contact(db_session, company_id=company.id, location_id=location.id, first_name="Mary", email="mary@company.com", phone="2321231234")

    assert audit_contacts(db_session) == []
    assert audit_locations(db_session) == []
    assert audit_companies(db_session) == []


def test_audit_detects_invalid_contact_email_phone_name_and_role(db_session) -> None:
    company = create_company(db_session, name="Bad Contact Audit Co")
    db_session.execute(
        text(
            "INSERT INTO contacts (company_id, first_name, last_name, email, phone, decision_role, is_primary_contact, is_active, created_at, updated_at) "
            "VALUES (:company_id, NULL, NULL, 'some', 'abc', 'BUYER', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        .bindparams(company_id=company.id)
    )
    db_session.commit()

    messages = issue_messages(audit_contacts(db_session))

    assert any("invalid email" in message for message in messages)
    assert any("missing first and last name" in message for message in messages)
    assert any("invalid phone" in message for message in messages)
    assert any("unsupported decision role" in message for message in messages)


def test_audit_detects_invalid_location_zip(db_session) -> None:
    company = create_company(db_session, name="Bad Location Audit Co")
    db_session.execute(
        text(
            "INSERT INTO locations (company_id, location_name, address_line_1, city, state, postal_code, location_type, territory_status, spectrum_relationship, is_primary_business_location, is_active, created_at, updated_at) "
            "VALUES (:company_id, '', '1 Main St', 'tampa', 'FL', '3360A', 'SMB', 'UNKNOWN', 'UNKNOWN', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        .bindparams(company_id=company.id)
    )
    db_session.commit()

    messages = issue_messages(audit_locations(db_session))

    assert any("invalid ZIP" in message for message in messages)
    assert any("missing or blank label" in message for message in messages)
    assert any("city requires normalization" in message for message in messages)


def test_audit_does_not_modify_data_by_default(db_session) -> None:
    company = create_company(db_session, name="No Modify Audit Co")
    db_session.execute(
        text(
            "INSERT INTO contacts (company_id, first_name, last_name, email, decision_role, is_primary_contact, is_active, created_at, updated_at) "
            "VALUES (:company_id, 'Mary', 'Smith', 'BAD', 'UNKNOWN', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        .bindparams(company_id=company.id)
    )
    db_session.commit()

    audit_contacts(db_session)
    stored_email = db_session.execute(text("SELECT email FROM contacts WHERE email = 'BAD'")).scalar_one()

    assert stored_email == "BAD"
