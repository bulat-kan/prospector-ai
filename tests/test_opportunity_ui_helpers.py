from datetime import date, datetime, timedelta
from decimal import Decimal

from app.constants import OPPORTUNITY_STAGE_LABELS
from app.crud import CompanyDTO, ContactDTO, LocationDTO
from app.enums import ContactRole, LocationType, OpportunityStage, SpectrumRelationship, TerritoryStatus
from app.opportunity_service import OpportunitySummary
from app.opportunity_ui_helpers import (
    CLOSED_WON_COMMISSION_WARNING,
    FOLLOW_UP_DUE_TODAY,
    FOLLOW_UP_FUTURE,
    FOLLOW_UP_NO_DATE,
    active_companies,
    available_contacts,
    available_locations,
    contact_label,
    filter_summaries,
    follow_up_filter_matches,
    follow_up_status,
    location_label,
    normalize_related_selection,
    opportunity_display_record,
    parse_money_input,
    stage_label,
    status_label,
    validate_product_rows,
    validate_score_value,
)


def summary(
    *,
    stage: OpportunityStage = OpportunityStage.QUALIFIED,
    next_action_date: date | None = date(2026, 7, 1),
    is_active: bool = True,
    name: str = "Account review",
) -> OpportunitySummary:
    return OpportunitySummary(
        id=123,
        company_id=10,
        company_name="Sunshine Plumbing LLC",
        location_id=20,
        location_name="Spring Hill office",
        primary_contact_id=30,
        primary_contact_name="John Carter",
        name=name,
        stage=stage,
        stage_display=stage_label(stage),
        product_names=("Business Mobile", "Seasonal Sports"),
        estimated_total_quantity=10,
        estimated_mrr=Decimal("500.00"),
        internet_probability=75,
        priority_score=85,
        next_action="Call owner",
        next_action_date=next_action_date,
        expected_close_date=date(2026, 7, 20),
        is_overdue=False,
        is_active=is_active,
    )


def company(company_id: int, active: bool = True) -> CompanyDTO:
    return CompanyDTO(
        id=company_id,
        name=f"Company {company_id}",
        website=None,
        main_phone=None,
        industry=None,
        lead_source=None,
        lead_source_legacy=None,
        referral_partner_id=None,
        referral_partner_name=None,
        referral_partner_organization=None,
        referral_partner_registered=False,
        referred_at=None,
        is_active=active,
        status=None,
        notes=None,
        source_system=None,
        external_id=None,
    )


def location(location_id: int, company_id: int, active: bool = True, location_type: LocationType = LocationType.SMB) -> LocationDTO:
    return LocationDTO(
        id=location_id,
        company_id=company_id,
        location_name="Main",
        address_line_1="100 Main St",
        address_line_2=None,
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=location_type,
        territory_status=TerritoryStatus.UNKNOWN,
        spectrum_relationship=SpectrumRelationship.UNKNOWN,
        is_active=active,
        inactive_reason=None,
        inactive_at=None,
        current_provider_notes=None,
        source_system=None,
        external_id=None,
    )


def contact(contact_id: int, company_id: int, active: bool = True) -> ContactDTO:
    return ContactDTO(
        id=contact_id,
        company_id=company_id,
        location_id=None,
        first_name="John",
        last_name="Carter",
        job_title="Owner",
        phone=None,
        email=None,
        decision_role=ContactRole.DECISION_MAKER,
        is_primary_contact=True,
        is_active=active,
        inactive_reason=None,
        inactive_at=None,
        notes=None,
        source_system=None,
        external_id=None,
    )


def test_stage_friendly_labels() -> None:
    assert stage_label(OpportunityStage.ATTEMPTING_CONTACT) == "Attempting Contact"
    assert stage_label("PROPOSAL_SENT") == "Proposal Sent"
    assert set(OPPORTUNITY_STAGE_LABELS.values()) >= {"Closed Won", "Closed Lost"}


def test_status_labels() -> None:
    assert status_label(summary()) == "Open"
    assert status_label(summary(stage=OpportunityStage.CLOSED_WON)) == "Closed Won"
    assert status_label(summary(stage=OpportunityStage.CLOSED_LOST)) == "Closed Lost"
    assert status_label(summary(is_active=False)) == "Archived"


def test_follow_up_statuses() -> None:
    today = date(2026, 7, 10)
    assert follow_up_status(summary(next_action_date=today - timedelta(days=3)), today) == "Overdue by 3 days"
    assert follow_up_status(summary(next_action_date=today), today) == FOLLOW_UP_DUE_TODAY
    assert follow_up_status(summary(next_action_date=today + timedelta(days=4)), today) == "Due in 4 days"
    assert follow_up_status(summary(next_action_date=today + timedelta(days=8)), today) == FOLLOW_UP_FUTURE
    assert follow_up_status(summary(next_action_date=None), today) == FOLLOW_UP_NO_DATE
    assert follow_up_status(summary(stage=OpportunityStage.CLOSED_WON, next_action_date=today - timedelta(days=3)), today) == "Closed"


def test_follow_up_filters() -> None:
    today = date(2026, 7, 10)
    assert follow_up_filter_matches(summary(next_action_date=today - timedelta(days=1)), "Overdue", today)
    assert follow_up_filter_matches(summary(next_action_date=today), "Due today", today)
    assert follow_up_filter_matches(summary(next_action_date=today + timedelta(days=3)), "Due this week", today)
    assert follow_up_filter_matches(summary(next_action_date=today + timedelta(days=9)), "Future", today)


def test_display_record_excludes_raw_ids_and_uses_friendly_values() -> None:
    record = opportunity_display_record(summary(), date(2026, 7, 10))

    assert "id" not in {key.lower() for key in record}
    assert record["Stage"] == "Qualified"
    assert record["Products"] == "Business Mobile, Seasonal Sports"
    assert record["Estimated MRR"] == "$500.00"


def test_filter_summaries_searches_name_and_company() -> None:
    today = date(2026, 7, 10)
    rows = (summary(name="Mobile Expansion"), summary(name="Security Review"))

    assert filter_summaries(rows, search="mobile", today=today)[0].name == "Mobile Expansion"
    assert len(filter_summaries(rows, search="sunshine", today=today)) == 2


def test_company_location_contact_options_filter_active_records() -> None:
    assert [item.id for item in active_companies((company(1), company(2, active=False)))] == [1]
    assert [item.id for item in available_locations(1, (location(1, 1), location(2, 1, active=False), location(3, 2)))] == [1]
    assert [item.id for item in available_contacts(1, (contact(1, 1), contact(2, 1, active=False), contact(3, 2)))] == [1]
    assert normalize_related_selection(99, {1, 2}) is None


def test_unassigned_location_and_contact_are_valid_options() -> None:
    assert normalize_related_selection(None, {1, 2}) is None


def test_location_and_contact_labels_are_friendly() -> None:
    assert location_label(location(1, 1, location_type=LocationType.BAR_RESTAURANT)) == "Main (B&R)"
    assert contact_label(contact(1, 1)) == "John Carter, Owner"


def test_score_validation_bounds() -> None:
    assert validate_score_value(0, "Priority score") is None
    assert validate_score_value(100, "Priority score") is None
    assert validate_score_value(-1, "Priority score") == "Priority score must be between 0 and 100."
    assert validate_score_value(101, "Priority score") == "Priority score must be between 0 and 100."


def test_product_row_validation() -> None:
    rows = [
        {"product_code": "BUSINESS_MOBILE", "estimated_quantity": 1, "estimated_incremental_mrr": "10.00"},
        {"product_code": "BUSINESS_MOBILE", "estimated_quantity": -1, "estimated_incremental_mrr": "-1.00"},
    ]
    errors = validate_product_rows(rows)

    assert errors["product_1"] == "This product is already included in the opportunity."
    assert errors["quantity_1"] == "Estimated quantity cannot be negative."
    assert errors["mrr_1"] == "Estimated incremental MRR cannot be negative."


def test_product_row_requires_at_least_one_product() -> None:
    assert validate_product_rows([])["products"] == "Select at least one product."


def test_money_parsing() -> None:
    assert parse_money_input("12.345", "Estimated incremental MRR") == (Decimal("12.35"), None)
    assert parse_money_input("-1", "Estimated incremental MRR")[1] == "Estimated incremental MRR cannot be negative."


def test_closed_won_warning_text_exists() -> None:
    assert "Commission is not earned" in CLOSED_WON_COMMISSION_WARNING
