from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.enums import (
    ActivityOutcome,
    ActivityType,
    ContactRole,
    LocationType,
    OpportunityStage,
    ProductCategory,
    ProductType,
    ProviderType,
    SaleStatus,
    ServiceRecordType,
    ServiceStatus,
    SpectrumRelationship,
    TaskStatus,
    TaskType,
    TerritoryStatus,
)
from app.models import (
    Activity,
    CommissionPlan,
    CommissionTier,
    Company,
    Contact,
    Location,
    Opportunity,
    Product,
    Sale,
    SaleItem,
    Service,
    Task,
)
from app.seed_demo import COMMISSION_PLAN_NAME, seed_configuration


def create_company(db_session, name: str = "Test Company LLC") -> Company:
    company = Company(name=name)
    db_session.add(company)
    db_session.commit()
    return company


def create_location(
    db_session,
    company: Company,
    *,
    name: str = "Office",
    address: str = "100 Main St",
    location_type: LocationType = LocationType.COMMERCIAL,
) -> Location:
    location = Location(
        company=company,
        location_name=name,
        address_line_1=address,
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=location_type,
    )
    db_session.add(location)
    db_session.commit()
    return location


def create_opportunity(db_session, company: Company, location: Location, **kwargs) -> Opportunity:
    opportunity = Opportunity(
        company=company,
        location=location,
        name=kwargs.pop("name", "Account Review"),
        **kwargs,
    )
    db_session.add(opportunity)
    db_session.commit()
    return opportunity


def test_company_and_locations(db_session) -> None:
    company = create_company(db_session)
    commercial = create_location(db_session, company, name="Business Office")
    home = create_location(
        db_session,
        company,
        name="Owner Home",
        address="200 Oak Ave",
        location_type=LocationType.SOHO,
    )

    db_session.refresh(company)

    assert {location.id for location in company.locations} == {commercial.id, home.id}
    assert commercial.company == company
    assert home.company == company


def test_existing_spectrum_customer_with_product_gaps(db_session) -> None:
    company = create_company(db_session, "Sunshine Plumbing LLC")
    location = create_location(db_session, company, name="Spring Hill office")
    services = [
        Service(
            company=company,
            location=location,
            record_type=ServiceRecordType.ACTIVE_SERVICE,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.INTERNET,
            service_status=ServiceStatus.ACTIVE,
            current_quantity=1,
        ),
        Service(
            company=company,
            location=location,
            record_type=ServiceRecordType.ACTIVE_SERVICE,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.VOICE,
            service_status=ServiceStatus.ACTIVE,
            current_quantity=2,
        ),
        Service(
            company=company,
            location=location,
            record_type=ServiceRecordType.PRODUCT_OPPORTUNITY,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.MOBILE,
            potential_quantity=8,
        ),
        Service(
            company=company,
            location=location,
            record_type=ServiceRecordType.PRODUCT_OPPORTUNITY,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.VIDEO,
            potential_quantity=2,
        ),
        Service(
            company=company,
            location=location,
            record_type=ServiceRecordType.PRODUCT_OPPORTUNITY,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.VOICE,
            potential_quantity=1,
        ),
    ]
    db_session.add_all(services)
    db_session.commit()

    active_services = db_session.scalars(
        select(Service).where(Service.record_type == ServiceRecordType.ACTIVE_SERVICE)
    ).all()
    product_opportunities = db_session.scalars(
        select(Service).where(Service.record_type == ServiceRecordType.PRODUCT_OPPORTUNITY)
    ).all()

    assert len(active_services) == 2
    assert len(product_opportunities) == 3
    assert {service.product_type for service in active_services} == {ProductType.INTERNET, ProductType.VOICE}
    assert {service.product_type for service in product_opportunities} == {
        ProductType.MOBILE,
        ProductType.VIDEO,
        ProductType.VOICE,
    }


def test_owner_home_soho_opportunity(db_session) -> None:
    company = create_company(db_session, "Sunshine Plumbing LLC")
    commercial = create_location(db_session, company, name="Spring Hill office")
    home = create_location(
        db_session,
        company,
        name="Owner Home",
        address="200 Oak Ave",
        location_type=LocationType.RESIDENTIAL,
    )
    owner = Contact(
        company=company,
        location=commercial,
        first_name="John",
        last_name="Carter",
        job_title="Owner",
        decision_role=ContactRole.DECISION_MAKER,
    )
    business_internet = Service(
        company=company,
        location=commercial,
        contact=owner,
        record_type=ServiceRecordType.ACTIVE_SERVICE,
        provider=ProviderType.SPECTRUM,
        product_type=ProductType.INTERNET,
        service_status=ServiceStatus.ACTIVE,
        current_quantity=1,
    )
    home_competitor = Service(
        company=company,
        location=home,
        contact=owner,
        record_type=ServiceRecordType.ACTIVE_SERVICE,
        provider=ProviderType.COMPETITOR,
        product_type=ProductType.INTERNET,
        account_type="RESIDENTIAL",
        service_status=ServiceStatus.ACTIVE,
        current_quantity=1,
    )
    soho_opportunity = Service(
        company=company,
        location=home,
        contact=owner,
        record_type=ServiceRecordType.PRODUCT_OPPORTUNITY,
        provider=ProviderType.SPECTRUM,
        product_type=ProductType.INTERNET,
        account_type="SOHO",
        potential_quantity=1,
    )
    db_session.add_all([owner, business_internet, home_competitor, soho_opportunity])
    db_session.commit()

    assert business_internet.location == commercial
    assert home_competitor.location == home
    assert soho_opportunity.location == home
    assert {service.id for service in commercial.services} == {business_internet.id}
    assert {service.id for service in home.services} == {home_competitor.id, soho_opportunity.id}


def test_opportunity_score_constraints_accept_0_through_100(db_session) -> None:
    company = create_company(db_session)
    location = create_location(db_session, company)

    low = create_opportunity(
        db_session,
        company,
        location,
        internet_probability=0,
        revenue_potential_score=0,
        cross_sell_score=0,
        priority_score=0,
    )
    high = create_opportunity(
        db_session,
        company,
        location,
        name="Max Score Review",
        internet_probability=100,
        revenue_potential_score=100,
        cross_sell_score=100,
        priority_score=100,
    )

    assert low.internet_probability == 0
    assert high.priority_score == 100


@pytest.mark.parametrize("score", [101, -1])
def test_opportunity_score_constraints_reject_invalid_values(db_session, score: int) -> None:
    company = create_company(db_session)
    location = create_location(db_session, company)
    opportunity = Opportunity(
        company=company,
        location=location,
        name=f"Invalid Score {score}",
        priority_score=score,
    )

    db_session.add(opportunity)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_sale_relationships_and_delete_orphan_cascade(db_session) -> None:
    company = create_company(db_session)
    location = create_location(db_session, company)
    opportunity = create_opportunity(db_session, company, location)
    sale = Sale(
        company=company,
        location=location,
        opportunity=opportunity,
        order_date=date.today(),
        status=SaleStatus.SUBMITTED,
        total_mrr=Decimal("499.97"),
        sale_items=[
            SaleItem(product_type=ProductType.INTERNET, quantity=1),
            SaleItem(product_type=ProductType.MOBILE, quantity=8),
            SaleItem(product_type=ProductType.VOICE, quantity=2),
        ],
    )
    db_session.add(sale)
    db_session.commit()

    sale_id = sale.id
    assert len(sale.sale_items) == 3
    assert all(item.sale == sale for item in sale.sale_items)

    db_session.delete(sale)
    db_session.commit()

    assert db_session.get(Sale, sale_id) is None
    assert db_session.scalars(select(SaleItem).where(SaleItem.sale_id == sale_id)).all() == []


def test_required_fields_raise_database_errors(db_session) -> None:
    db_session.add(Company())
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(
        Location(
            address_line_1="100 Main St",
            city="Spring Hill",
            state="FL",
            postal_code="34609",
            location_type=LocationType.COMMERCIAL,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    company = create_company(db_session)
    db_session.add(
        Service(
            company=company,
            record_type=ServiceRecordType.ACTIVE_SERVICE,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.INTERNET,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(SaleItem(product_type=ProductType.INTERNET))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_task_and_activity_relationships(db_session) -> None:
    company = create_company(db_session)
    location = create_location(db_session, company)
    contact = Contact(
        company=company,
        location=location,
        first_name="John",
        last_name="Carter",
        decision_role=ContactRole.DECISION_MAKER,
    )
    opportunity = Opportunity(
        company=company,
        location=location,
        primary_contact=contact,
        name="Sunshine Plumbing Account Review",
        stage=OpportunityStage.CONTACT_ATTEMPTED,
    )
    activity = Activity(
        company=company,
        location=location,
        contact=contact,
        opportunity=opportunity,
        activity_type=ActivityType.DOOR_KNOCK,
        activity_at=datetime.now(UTC),
        outcome=ActivityOutcome.DECISION_MAKER_REACHED,
        follow_up_required=True,
    )
    task = Task(
        company=company,
        location=location,
        contact=contact,
        opportunity=opportunity,
        task_type=TaskType.CALL,
        title="Call owner to review mobile pricing",
        due_at=datetime.now(UTC) + timedelta(days=1),
        status=TaskStatus.OPEN,
    )
    db_session.add_all([contact, opportunity, activity, task])
    db_session.commit()

    assert activity.company == company
    assert activity.location == location
    assert activity.contact == contact
    assert activity.opportunity == opportunity
    assert task.company == company
    assert task.location == location
    assert task.contact == contact
    assert task.opportunity == opportunity
    assert activity in company.activities
    assert task in company.tasks
    assert activity in location.activities
    assert task in location.tasks
    assert activity in contact.activities
    assert task in contact.tasks
    assert activity in opportunity.activities
    assert task in opportunity.tasks


def test_timestamp_behavior(db_session) -> None:
    company = create_company(db_session)

    assert company.created_at is not None
    assert company.updated_at is not None

    company.notes = "Updated notes"
    db_session.commit()
    db_session.refresh(company)

    assert company.updated_at is not None
    assert company.updated_at >= company.created_at


def test_product_catalog_seeded_correctly(db_session) -> None:
    products_created, plan_created, tiers_created = seed_configuration(db_session)

    products = db_session.scalars(select(Product).order_by(Product.code)).all()
    product_by_code = {product.code: product for product in products}

    assert products_created == 7
    assert plan_created is True
    assert tiers_created == 6
    assert len(products) == 7
    assert set(product_by_code) == {
        "BUSINESS_INTERNET",
        "BUSINESS_MOBILE",
        "BUSINESS_VIDEO",
        "BUSINESS_VOICE",
        "INVINCIBLE_WIFI",
        "UNLIMITED_PLUS",
        "WIB",
    }

    internet = product_by_code["BUSINESS_INTERNET"]
    assert internet.category == ProductCategory.TIERED
    assert internet.counts_as_internet_connect is True
    assert internet.counts_as_connected_unit is True
    assert internet.creates_mrr is True
    assert internet.uses_tiered_rates is True

    wib = product_by_code["WIB"]
    assert wib.category == ProductCategory.A_LA_CARTE
    assert wib.counts_as_connected_unit is False
    assert wib.creates_mrr is True
    assert wib.uses_flat_rate is True
    assert wib.flat_commission_amount == Decimal("100.00")

    unlimited_plus = product_by_code["UNLIMITED_PLUS"]
    assert unlimited_plus.creates_mrr is False
    assert unlimited_plus.counts_as_connected_unit is False
    assert unlimited_plus.flat_commission_amount == Decimal("50.00")


def test_commission_plan_seeded_correctly(db_session) -> None:
    seed_configuration(db_session)

    plan = db_session.scalar(select(CommissionPlan).where(CommissionPlan.name == COMMISSION_PLAN_NAME))

    assert plan is not None
    assert plan.name == "Spectrum Business AE 2026"
    assert plan.effective_start == date(2026, 1, 1)
    assert plan.effective_end is None
    assert plan.active is True
    assert plan.minimum_internet_threshold == 5
    assert plan.bonus_unit_threshold == 20
    assert plan.bonus_percentage == Decimal("7.50")
    assert [tier.tier_name for tier in plan.tiers] == ["5-9", "10-14", "15-19", "20-24", "25-29", "30+"]


def test_commission_tier_lookup_works(db_session) -> None:
    seed_configuration(db_session)
    plan = db_session.scalar(select(CommissionPlan).where(CommissionPlan.name == COMMISSION_PLAN_NAME))
    assert plan is not None

    tier = db_session.scalar(
        select(CommissionTier)
        .where(
            CommissionTier.commission_plan_id == plan.id,
            CommissionTier.minimum_internet <= 21,
            (CommissionTier.maximum_internet.is_(None)) | (CommissionTier.maximum_internet >= 21),
        )
        .order_by(CommissionTier.display_order)
    )

    assert tier is not None
    assert tier.tier_name == "20-24"
    assert tier.internet_rate == Decimal("250.00")
    assert tier.mobile_rate == Decimal("200.00")
    assert tier.voice_rate == Decimal("160.00")
    assert tier.video_rate == Decimal("140.00")
    assert tier.mrr_percentage == Decimal("80.00")


def test_products_remain_unique(db_session) -> None:
    seed_configuration(db_session)
    db_session.add(
        Product(
            code="BUSINESS_INTERNET",
            name="Duplicate Business Internet",
            category=ProductCategory.TIERED,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_seed_configuration_twice_creates_no_duplicates(db_session) -> None:
    first_result = seed_configuration(db_session)
    second_result = seed_configuration(db_session)

    product_count = len(db_session.scalars(select(Product)).all())
    plan_count = len(db_session.scalars(select(CommissionPlan)).all())
    tier_count = len(db_session.scalars(select(CommissionTier)).all())

    assert first_result == (7, True, 6)
    assert second_result == (0, False, 0)
    assert product_count == 7
    assert plan_count == 1
    assert tier_count == 6
