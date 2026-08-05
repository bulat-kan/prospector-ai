from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm.exc import DetachedInstanceError

from app.analytics import calculate_monthly_commission
from app.crud import RecordNotFoundError
from app.enums import LocationType, OpportunityStage
from app.models import Company, Contact, Location, Opportunity, OpportunityProduct, Product
from app.opportunity_service import (
    DuplicateOpportunityProductError,
    OpportunityProductInput,
    OpportunityValidationError,
    add_opportunity_product,
    archive_opportunity,
    create_opportunity,
    create_opportunity_result_with_products,
    create_opportunity_with_products,
    get_opportunity,
    is_closed_stage,
    is_open_stage,
    list_opportunities,
    list_opportunity_products,
    normalize_opportunity_stage,
    opportunity_to_detail,
    opportunity_to_summary,
    remove_opportunity_product,
    restore_opportunity,
    update_opportunity,
    update_opportunity_product,
)
from app.seed_demo import COMPANY_NAME, seed_configuration, seed_demo, seed_demo_opportunity_products, seed_demo_sales


def seed_products(db_session):
    seed_configuration(db_session)
    return {product.code: product for product in db_session.scalars(select(Product)).all()}


def create_company(db_session, *, name: str = "Opportunity Test LLC", active: bool = True) -> Company:
    company = Company(name=name, is_active=active)
    db_session.add(company)
    db_session.commit()
    return company


def create_location(
    db_session,
    company: Company,
    *,
    active: bool = True,
    name: str = "Main Office",
    location_type: LocationType = LocationType.SMB,
) -> Location:
    location = Location(
        company=company,
        location_name=name,
        address_line_1=f"{name} 100 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=location_type,
        is_active=active,
    )
    db_session.add(location)
    db_session.commit()
    return location


def create_contact(db_session, company: Company, location: Location | None = None, *, active: bool = True) -> Contact:
    contact = Contact(
        company=company,
        location=location,
        first_name="Jordan",
        last_name="Smith",
        email=f"jordan{company.id}@example.com",
        is_active=active,
    )
    db_session.add(contact)
    db_session.commit()
    return contact


def create_valid_opportunity(db_session, company: Company | None = None, **kwargs) -> Opportunity:
    company = company or create_company(db_session)
    defaults = {
        "company_id": company.id,
        "name": "Account Expansion",
        "stage": OpportunityStage.QUALIFIED,
        "next_action": "Call decision maker",
        "next_action_date": date(2026, 7, 10),
    }
    defaults.update(kwargs)
    return create_opportunity(db_session, **defaults)


@pytest.mark.parametrize(
    "stage",
    [
        OpportunityStage.NEW,
        OpportunityStage.ATTEMPTING_CONTACT,
        OpportunityStage.CONNECTED,
        OpportunityStage.QUALIFIED,
        OpportunityStage.APPOINTMENT_SET,
        OpportunityStage.NEEDS_ANALYSIS,
        OpportunityStage.PROPOSAL_SENT,
        OpportunityStage.NEGOTIATION,
        OpportunityStage.PENDING_INSTALL,
        OpportunityStage.CLOSED_WON,
        OpportunityStage.CLOSED_LOST,
    ],
)
def test_every_required_new_stage_is_accepted(stage: OpportunityStage) -> None:
    assert normalize_opportunity_stage(stage) == stage


def test_invalid_stage_rejected() -> None:
    with pytest.raises(OpportunityValidationError):
        normalize_opportunity_stage("NOT_A_STAGE")


@pytest.mark.parametrize(
    ("legacy", "standard"),
    [
        ("APPOINTMENT", OpportunityStage.APPOINTMENT_SET),
        ("QUOTE", OpportunityStage.PROPOSAL_SENT),
        ("WON", OpportunityStage.CLOSED_WON),
        ("LOST", OpportunityStage.CLOSED_LOST),
        ("CONTACT_ATTEMPTED", OpportunityStage.ATTEMPTING_CONTACT),
        ("RESEARCHING", OpportunityStage.NEW),
    ],
)
def test_legacy_stages_map_safely(legacy: str, standard: OpportunityStage) -> None:
    assert normalize_opportunity_stage(legacy) == standard


def test_closed_and_open_stage_helpers() -> None:
    assert is_closed_stage(OpportunityStage.CLOSED_WON)
    assert is_closed_stage(OpportunityStage.CLOSED_LOST)
    assert not is_closed_stage(OpportunityStage.QUALIFIED)
    assert is_open_stage(OpportunityStage.NEW)
    assert is_open_stage(OpportunityStage.PENDING_INSTALL)
    assert not is_open_stage(OpportunityStage.CLOSED_LOST)


def test_create_opportunity_with_company(db_session) -> None:
    company = create_company(db_session)
    opportunity = create_valid_opportunity(db_session, company)

    assert opportunity.company_id == company.id
    assert opportunity.location_id is None


def test_create_opportunity_with_valid_location_and_contact(db_session) -> None:
    company = create_company(db_session)
    location = create_location(db_session, company)
    contact = create_contact(db_session, company, location)

    opportunity = create_valid_opportunity(
        db_session,
        company,
        location_id=location.id,
        primary_contact_id=contact.id,
    )

    assert opportunity.location == location
    assert opportunity.primary_contact == contact


def test_inactive_company_location_and_contact_rejected(db_session) -> None:
    inactive_company = create_company(db_session, active=False)
    with pytest.raises(OpportunityValidationError, match="inactive"):
        create_valid_opportunity(db_session, inactive_company)

    company = create_company(db_session, name="Active Company")
    inactive_location = create_location(db_session, company, active=False)
    inactive_contact = create_contact(db_session, company, active=False)
    with pytest.raises(OpportunityValidationError, match="Location"):
        create_valid_opportunity(db_session, company, location_id=inactive_location.id)
    with pytest.raises(OpportunityValidationError, match="Contact"):
        create_valid_opportunity(db_session, company, primary_contact_id=inactive_contact.id)


def test_location_and_contact_from_another_company_rejected(db_session) -> None:
    company = create_company(db_session, name="Company A")
    other = create_company(db_session, name="Company B")
    other_location = create_location(db_session, other)
    other_contact = create_contact(db_session, other)

    with pytest.raises(OpportunityValidationError, match="Location"):
        create_valid_opportunity(db_session, company, location_id=other_location.id)
    with pytest.raises(OpportunityValidationError, match="Contact"):
        create_valid_opportunity(db_session, company, primary_contact_id=other_contact.id)


def test_blank_opportunity_name_rejected(db_session) -> None:
    company = create_company(db_session)
    with pytest.raises(OpportunityValidationError, match="Opportunity name"):
        create_valid_opportunity(db_session, company, name=" ")


def test_open_stage_follow_up_rules(db_session) -> None:
    company = create_company(db_session)
    with pytest.raises(OpportunityValidationError, match="next action"):
        create_opportunity(db_session, company_id=company.id, name="Missing Action", stage=OpportunityStage.QUALIFIED, next_action_date=date(2026, 7, 1))
    with pytest.raises(OpportunityValidationError, match="next action date"):
        create_opportunity(db_session, company_id=company.id, name="Missing Date", stage=OpportunityStage.QUALIFIED, next_action="Call")


def test_closed_won_allows_no_next_action_and_closed_lost_requires_reason(db_session) -> None:
    company = create_company(db_session)
    won = create_opportunity(db_session, company_id=company.id, name="Won Deal", stage=OpportunityStage.CLOSED_WON)

    assert won.next_action is None
    with pytest.raises(OpportunityValidationError, match="lost reason"):
        create_opportunity(db_session, company_id=company.id, name="Lost Deal", stage=OpportunityStage.CLOSED_LOST)
    lost = create_opportunity(
        db_session,
        company_id=company.id,
        name="Lost Deal",
        stage=OpportunityStage.CLOSED_LOST,
        lost_reason="Competitor renewal",
    )
    assert lost.lost_reason == "Competitor renewal"


@pytest.mark.parametrize("score", [0, 100])
def test_score_bounds_accepted(db_session, score: int) -> None:
    company = create_company(db_session)
    opportunity = create_valid_opportunity(
        db_session,
        company,
        internet_probability=score,
        revenue_potential_score=score,
        cross_sell_score=score,
        priority_score=score,
    )

    assert opportunity.priority_score == score


@pytest.mark.parametrize("score", [-1, 101])
def test_score_bounds_rejected(db_session, score: int) -> None:
    company = create_company(db_session)
    with pytest.raises(OpportunityValidationError):
        create_valid_opportunity(db_session, company, priority_score=score)


def test_create_opportunity_with_one_and_multiple_products(db_session) -> None:
    products = seed_products(db_session)
    company = create_company(db_session)
    one = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        name="One Product",
        stage=OpportunityStage.QUALIFIED,
        next_action="Call",
        next_action_date=date(2026, 7, 1),
        products=[OpportunityProductInput(product_id=products["BUSINESS_INTERNET"].id, estimated_quantity=1)],
    )
    many = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        name="Many Products",
        stage=OpportunityStage.QUALIFIED,
        next_action="Call",
        next_action_date=date(2026, 7, 1),
        products=[
            OpportunityProductInput(product_code="BUSINESS_MOBILE", estimated_quantity=8),
            OpportunityProductInput(product_code="BUSINESS_VIDEO", estimated_quantity=2),
        ],
    )

    assert len(one.products) == 1
    assert {row.product_code for row in many.products} == {"BUSINESS_MOBILE", "BUSINESS_VIDEO"}


def test_created_opportunity_result_is_detached_safe_after_session_close(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session, name="Sunshine Plumbing LLC")
    company_id = company.id

    created = create_opportunity_result_with_products(
        db_session,
        company_id=company_id,
        name="Mobile & Internet Upgrade",
        stage=OpportunityStage.QUALIFIED,
        next_action="Call owner",
        next_action_date=date(2026, 7, 1),
        products=[
            OpportunityProductInput(product_code="BUSINESS_INTERNET", estimated_quantity=1),
            OpportunityProductInput(product_code="BUSINESS_MOBILE", estimated_quantity=8),
        ],
    )

    db_session.expunge_all()

    assert created.opportunity_id > 0
    assert created.opportunity_name == "Mobile & Internet Upgrade"
    assert created.company_id == company_id
    assert created.company_name == "Sunshine Plumbing LLC"


def test_created_opportunity_orm_return_loads_company_before_detach(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session, name="Detached Safe LLC")

    opportunity = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        name="Account Review",
        stage=OpportunityStage.QUALIFIED,
        next_action="Call",
        next_action_date=date(2026, 7, 1),
        products=[OpportunityProductInput(product_code="BUSINESS_INTERNET", estimated_quantity=1)],
    )

    db_session.expunge_all()

    try:
        assert opportunity.id > 0
        assert opportunity.name == "Account Review"
        assert opportunity.company.name == "Detached Safe LLC"
    except DetachedInstanceError as exc:
        pytest.fail(f"Opportunity creation returned a detached object requiring lazy load: {exc}")


def test_duplicate_product_negative_values_and_missing_catalog_rejected(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session)
    with pytest.raises(DuplicateOpportunityProductError):
        create_opportunity_with_products(
            db_session,
            company_id=company.id,
            name="Duplicate Product",
            stage=OpportunityStage.QUALIFIED,
            next_action="Call",
            next_action_date=date(2026, 7, 1),
            products=[
                OpportunityProductInput(product_code="BUSINESS_MOBILE", estimated_quantity=1),
                OpportunityProductInput(product_code="BUSINESS_MOBILE", estimated_quantity=2),
            ],
        )
    with pytest.raises(OpportunityValidationError, match="quantity"):
        create_opportunity_with_products(
            db_session,
            company_id=company.id,
            name="Negative Quantity",
            stage=OpportunityStage.QUALIFIED,
            next_action="Call",
            next_action_date=date(2026, 7, 1),
            products=[OpportunityProductInput(product_code="BUSINESS_MOBILE", estimated_quantity=-1)],
        )
    with pytest.raises(OpportunityValidationError, match="MRR"):
        create_opportunity_with_products(
            db_session,
            company_id=company.id,
            name="Negative MRR",
            stage=OpportunityStage.QUALIFIED,
            next_action="Call",
            next_action_date=date(2026, 7, 1),
            products=[OpportunityProductInput(product_code="BUSINESS_MOBILE", estimated_incremental_mrr=Decimal("-1.00"))],
        )
    with pytest.raises(RecordNotFoundError):
        create_opportunity_with_products(
            db_session,
            company_id=company.id,
            name="Missing Product",
            stage=OpportunityStage.QUALIFIED,
            next_action="Call",
            next_action_date=date(2026, 7, 1),
            products=[OpportunityProductInput(product_code="NOPE")],
        )


def test_seasonal_sports_everpass_and_inactive_product_rules(db_session) -> None:
    products = seed_products(db_session)
    company = create_company(db_session)
    opportunity = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        name="Sports Package",
        stage=OpportunityStage.QUALIFIED,
        next_action="Visit",
        next_action_date=date(2026, 7, 1),
        products=[
            OpportunityProductInput(product_id=products["SEASONAL_SPORTS"].id, estimated_quantity=1),
            OpportunityProductInput(product_id=products["EVERPASS"].id, estimated_quantity=1),
        ],
    )
    products["SECURITY"].active = False
    db_session.commit()

    assert {row.product_code for row in opportunity.products} == {"SEASONAL_SPORTS", "EVERPASS"}
    with pytest.raises(OpportunityValidationError, match="inactive"):
        add_opportunity_product(db_session, opportunity.id, OpportunityProductInput(product_code="SECURITY"))


def test_bar_restaurant_location_can_use_sports_products(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session, name="Demo Sports Grill")
    location = create_location(db_session, company, name="Demo Sports Grill", location_type=LocationType.BAR_RESTAURANT)

    opportunity = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        location_id=location.id,
        name="B&R Sports Package",
        stage=OpportunityStage.QUALIFIED,
        next_action="Review sports package",
        next_action_date=date(2026, 7, 1),
        products=[
            OpportunityProductInput(product_code="BUSINESS_INTERNET", estimated_quantity=1),
            OpportunityProductInput(product_code="BUSINESS_VIDEO", estimated_quantity=1),
            OpportunityProductInput(product_code="SEASONAL_SPORTS", estimated_quantity=1),
            OpportunityProductInput(product_code="EVERPASS", estimated_quantity=1),
        ],
    )

    assert location.location_type == LocationType.BAR_RESTAURANT
    assert {row.product_code for row in opportunity.products} == {
        "BUSINESS_INTERNET",
        "BUSINESS_VIDEO",
        "SEASONAL_SPORTS",
        "EVERPASS",
    }


def test_atomic_creation_rolls_back_on_invalid_product(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session)
    before = db_session.scalar(select(func.count()).select_from(Opportunity))

    with pytest.raises(RecordNotFoundError):
        create_opportunity_with_products(
            db_session,
            company_id=company.id,
            name="Rollback Deal",
            stage=OpportunityStage.QUALIFIED,
            next_action="Call",
            next_action_date=date(2026, 7, 1),
            products=[OpportunityProductInput(product_code="BUSINESS_MOBILE"), OpportunityProductInput(product_code="NOPE")],
        )

    after = db_session.scalar(select(func.count()).select_from(Opportunity))
    assert after == before


def test_update_archive_restore_and_archived_filtering(db_session) -> None:
    company = create_company(db_session)
    opportunity = create_valid_opportunity(db_session, company)
    updated = update_opportunity(db_session, opportunity.id, name="Updated Deal", priority_score=90)

    assert updated.name == "Updated Deal"
    archived = archive_opportunity(db_session, opportunity.id)
    assert archived.is_active is False
    assert list_opportunities(db_session) == ()
    assert list_opportunities(db_session, include_archived=True)[0].id == opportunity.id
    restored = restore_opportunity(db_session, opportunity.id)
    assert restored.is_active is True


def test_product_crud_and_missing_records(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session)
    opportunity = create_valid_opportunity(db_session, company)
    row = add_opportunity_product(
        db_session,
        opportunity.id,
        OpportunityProductInput(product_code="BUSINESS_MOBILE", estimated_quantity=8, estimated_incremental_mrr=Decimal("400.00")),
    )
    updated = update_opportunity_product(db_session, row.id, estimated_quantity=9)

    assert updated.estimated_quantity == 9
    assert len(list_opportunity_products(db_session, opportunity.id)) == 1
    remove_opportunity_product(db_session, row.id)
    assert list_opportunity_products(db_session, opportunity.id) == ()
    with pytest.raises(RecordNotFoundError):
        get_opportunity(db_session, 9999)
    with pytest.raises(RecordNotFoundError):
        update_opportunity_product(db_session, 9999, estimated_quantity=1)


def test_rollback_works_after_failure(db_session) -> None:
    company = create_company(db_session)
    with pytest.raises(OpportunityValidationError):
        create_valid_opportunity(db_session, company, name="")
    valid = create_valid_opportunity(db_session, company, name="Valid After Failure")

    assert valid.id is not None


def test_listing_filters_and_ordering(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session, name="Filter Company")
    other = create_company(db_session, name="Other Company")
    location = create_location(db_session, company)
    mobile_deal = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        location_id=location.id,
        name="Mobile Deal",
        stage=OpportunityStage.QUALIFIED,
        next_action="Call",
        next_action_date=date(2026, 7, 5),
        priority_score=80,
        products=[OpportunityProductInput(product_code="BUSINESS_MOBILE", estimated_quantity=8)],
    )
    internet_deal = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        name="Internet Deal",
        stage=OpportunityStage.PROPOSAL_SENT,
        next_action="Send proposal",
        next_action_date=date(2026, 7, 5),
        priority_score=95,
        products=[OpportunityProductInput(product_code="BUSINESS_INTERNET", estimated_quantity=2)],
    )
    future = create_valid_opportunity(db_session, other, name="Future", next_action_date=date(2026, 8, 1), priority_score=100)

    listed = list_opportunities(db_session, today=date(2026, 7, 10))

    assert [opportunity.id for opportunity in listed[:2]] == [internet_deal.id, mobile_deal.id]
    assert list_opportunities(db_session, company_id=company.id, today=date(2026, 7, 10)) == (internet_deal, mobile_deal)
    assert list_opportunities(db_session, location_id=location.id)[0].id == mobile_deal.id
    assert list_opportunities(db_session, stage=OpportunityStage.PROPOSAL_SENT)[0].id == internet_deal.id
    assert list_opportunities(db_session, follow_up_due_before=date(2026, 7, 6), today=date(2026, 7, 10)) == (internet_deal, mobile_deal)
    assert list_opportunities(db_session, minimum_priority_score=100)[0].id == future.id
    assert list_opportunities(db_session, product_code="BUSINESS_MOBILE")[0].id == mobile_deal.id


def test_same_company_can_have_multiple_opportunities_and_duplicate_names(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session, name="Multiple Opportunity Company")

    first = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        name="Mobile & Internet Upgrade",
        stage=OpportunityStage.QUALIFIED,
        next_action="Review mobile pricing",
        next_action_date=date(2026, 7, 10),
        products=[OpportunityProductInput(product_code="BUSINESS_MOBILE", estimated_quantity=8)],
    )
    second = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        name="TV Expansion",
        stage=OpportunityStage.QUALIFIED,
        next_action="Review TV package",
        next_action_date=date(2026, 7, 11),
        products=[OpportunityProductInput(product_code="BUSINESS_VIDEO", estimated_quantity=2)],
    )
    duplicate_name = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        name="Mobile & Internet Upgrade",
        stage=OpportunityStage.QUALIFIED,
        next_action="Follow up later",
        next_action_date=date(2026, 7, 12),
        products=[OpportunityProductInput(product_code="BUSINESS_INTERNET", estimated_quantity=1)],
    )

    loaded = get_opportunity(db_session, duplicate_name.id)
    opportunities = list_opportunities(db_session, company_id=company.id)

    assert loaded.id == duplicate_name.id
    assert {opportunity.id for opportunity in opportunities} == {first.id, second.id, duplicate_name.id}
    assert [opportunity.name for opportunity in opportunities].count("Mobile & Internet Upgrade") == 2


def test_dtos_have_friendly_values_and_internal_ids(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session, name="DTO Company")
    location = create_location(db_session, company, name="DTO Office")
    contact = create_contact(db_session, company, location)
    opportunity = create_opportunity_with_products(
        db_session,
        company_id=company.id,
        location_id=location.id,
        primary_contact_id=contact.id,
        name="DTO Deal",
        stage=OpportunityStage.PROPOSAL_SENT,
        next_action="Review",
        next_action_date=date(2026, 7, 1),
        estimated_mrr=Decimal("100.50"),
        products=[OpportunityProductInput(product_code="BUSINESS_MOBILE", estimated_quantity=8)],
    )

    summary = opportunity_to_summary(opportunity, today=date(2026, 7, 2))
    detail = opportunity_to_detail(opportunity, today=date(2026, 7, 2))

    assert summary.id == opportunity.id
    assert summary.company_name == "DTO Company"
    assert summary.location_name == "DTO Office"
    assert summary.stage_display == "Proposal Sent"
    assert summary.product_names == ("Business Mobile",)
    assert "PROPOSAL_SENT" not in summary.stage_display
    assert detail.products[0].product_id is not None


def test_seed_idempotency_and_sunshine_opportunity_browseable(db_session) -> None:
    seed_configuration(db_session)
    assert seed_demo(db_session) is True
    created_first = seed_demo_opportunity_products(db_session)
    assert seed_demo(db_session) is False
    created_second = seed_demo_opportunity_products(db_session)

    company = db_session.scalar(select(Company).where(Company.name == COMPANY_NAME))
    assert company is not None
    opportunities = list_opportunities(db_session, company_id=company.id)
    assert any(opportunity.name == "Sunshine Plumbing Account Review" for opportunity in opportunities)
    assert created_first == 3
    assert created_second == 0
    assert db_session.scalar(select(func.count()).select_from(OpportunityProduct)) == 3


def test_legacy_stage_migration_preserves_records(db_session) -> None:
    company = create_company(db_session)
    db_session.execute(
        text(
            "INSERT INTO opportunities (company_id, name, stage, internet_probability, revenue_potential_score, "
            "cross_sell_score, priority_score, estimated_internet_units, estimated_mobile_lines, "
            "estimated_voice_units, estimated_video_units, is_active, created_at, updated_at) "
            "VALUES (:company_id, 'Legacy Deal', 'QUOTE', 0, 0, 0, 0, 0, 0, 0, 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"company_id": company.id},
    )
    db_session.execute(text("UPDATE opportunities SET stage = 'PROPOSAL_SENT' WHERE stage = 'QUOTE'"))
    db_session.commit()

    opportunity = db_session.scalar(select(Opportunity).where(Opportunity.name == "Legacy Deal"))
    assert opportunity is not None
    assert opportunity.stage == OpportunityStage.PROPOSAL_SENT


def test_demo_sales_commission_output_unchanged(db_session) -> None:
    seed_configuration(db_session)
    seed_demo(db_session)
    seed_demo_opportunity_products(db_session)
    seed_demo_sales(db_session)

    analytics = calculate_monthly_commission(db_session, 2026, 7)

    assert analytics.commission_result.estimated_payout == Decimal("2200.25")
