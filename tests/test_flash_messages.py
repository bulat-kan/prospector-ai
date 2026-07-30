import pytest

from app.crud import (
    RecordNotFoundError,
    archive_company,
    create_company,
    create_contact,
    create_location,
    deactivate_contact,
    deactivate_location,
    restore_company,
    restore_contact,
    restore_location,
)
from app.enums import LocationType
from app.form_state import pop_flash_message, set_flash_message


def test_company_archive_sets_expected_success_message(db_session) -> None:
    company = create_company(db_session, name="Flash Archive Co")
    state: dict[str, object] = {}

    archive_company(db_session, company.id)
    set_flash_message(state, "Company archived.")

    assert pop_flash_message(state) == ("Company archived.", "success")


def test_company_restore_sets_expected_success_message(db_session) -> None:
    company = create_company(db_session, name="Flash Restore Co")
    archive_company(db_session, company.id)
    state: dict[str, object] = {}

    restore_company(db_session, company.id)
    set_flash_message(state, "Company restored.")

    assert pop_flash_message(state) == ("Company restored.", "success")


def test_contact_deactivate_sets_expected_success_message(db_session) -> None:
    company = create_company(db_session, name="Flash Contact Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Casey")
    state: dict[str, object] = {}

    deactivate_contact(db_session, contact.id, "No longer with company")
    set_flash_message(state, "Contact marked as no longer with company.")

    assert pop_flash_message(state) == ("Contact marked as no longer with company.", "success")


def test_contact_restore_sets_expected_success_message(db_session) -> None:
    company = create_company(db_session, name="Flash Contact Restore Co")
    contact = create_contact(db_session, company_id=company.id, first_name="Casey")
    deactivate_contact(db_session, contact.id, "No longer with company")
    state: dict[str, object] = {}

    restore_contact(db_session, contact.id)
    set_flash_message(state, "Contact restored.")

    assert pop_flash_message(state) == ("Contact restored.", "success")


def test_location_deactivate_sets_expected_success_message(db_session) -> None:
    company = create_company(db_session, name="Flash Location Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="100 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.SMB,
    )
    state: dict[str, object] = {}

    deactivate_location(db_session, location.id, "Closed")
    set_flash_message(state, "Location marked inactive.")

    assert pop_flash_message(state) == ("Location marked inactive.", "success")


def test_location_restore_sets_expected_success_message(db_session) -> None:
    company = create_company(db_session, name="Flash Location Restore Co")
    location = create_location(
        db_session,
        company_id=company.id,
        address_line_1="110 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.SMB,
    )
    deactivate_location(db_session, location.id, "Closed")
    state: dict[str, object] = {}

    restore_location(db_session, location.id)
    set_flash_message(state, "Location restored.")

    assert pop_flash_message(state) == ("Location restored.", "success")


def test_failed_crud_action_does_not_set_success_message(db_session) -> None:
    state: dict[str, object] = {}

    with pytest.raises(RecordNotFoundError):
        archive_company(db_session, 999)

    assert pop_flash_message(state) is None


def test_contact_success_message_includes_full_name() -> None:
    state: dict[str, object] = {}

    set_flash_message(state, '✅ Contact "Mary Johnson" added successfully.')

    assert pop_flash_message(state) == ('✅ Contact "Mary Johnson" added successfully.', "success")


def test_location_success_message_includes_generated_label() -> None:
    state: dict[str, object] = {}

    set_flash_message(state, '✅ Location "Tampa Office" added successfully.')

    assert pop_flash_message(state) == ('✅ Location "Tampa Office" added successfully.', "success")
