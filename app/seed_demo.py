from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
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


COMPANY_NAME = "Sunshine Plumbing LLC"
COMMISSION_PLAN_NAME = "Spectrum Business AE 2026"
DEMO_SALES_MARKER = "July 2026 analytics demo"


PRODUCTS = [
    {
        "code": "BUSINESS_INTERNET",
        "name": "Business Internet",
        "category": ProductCategory.TIERED,
        "description": "Spectrum Business Internet service.",
        "counts_as_internet_connect": True,
        "counts_as_connected_unit": True,
        "creates_mrr": True,
        "uses_tiered_rates": True,
        "available_soho": True,
    },
    {
        "code": "BUSINESS_MOBILE",
        "name": "Business Mobile",
        "category": ProductCategory.TIERED,
        "description": "Spectrum Mobile lines for business customers.",
        "counts_as_connected_unit": True,
        "creates_mrr": True,
        "uses_tiered_rates": True,
        "available_soho": True,
    },
    {
        "code": "BUSINESS_VOICE",
        "name": "Business Voice",
        "category": ProductCategory.TIERED,
        "description": "Spectrum Business Voice service.",
        "counts_as_connected_unit": True,
        "creates_mrr": True,
        "uses_tiered_rates": True,
        "available_soho": True,
    },
    {
        "code": "BUSINESS_VIDEO",
        "name": "Business Video",
        "category": ProductCategory.TIERED,
        "description": "Spectrum Business Video service.",
        "counts_as_connected_unit": True,
        "creates_mrr": True,
        "uses_tiered_rates": True,
        "available_soho": True,
    },
    {
        "code": "WIB",
        "name": "Wireless Internet Backup",
        "category": ProductCategory.A_LA_CARTE,
        "description": "Wireless Internet Backup add-on.",
        "creates_mrr": True,
        "uses_flat_rate": True,
        "requires_existing_internet": True,
        "flat_commission_amount": Decimal("100.00"),
    },
    {
        "code": "INVINCIBLE_WIFI",
        "name": "Invincible WiFi",
        "category": ProductCategory.A_LA_CARTE,
        "description": "Invincible WiFi add-on.",
        "creates_mrr": True,
        "uses_flat_rate": True,
        "requires_existing_internet": True,
        "flat_commission_amount": Decimal("100.00"),
    },
    {
        "code": "UNLIMITED_PLUS",
        "name": "Unlimited Plus",
        "category": ProductCategory.A_LA_CARTE,
        "description": "Unlimited Plus add-on.",
        "creates_mrr": False,
        "uses_flat_rate": True,
        "flat_commission_amount": Decimal("50.00"),
    },
]

LEGACY_PRODUCT_CODES = {
    "WIRELESS_INTERNET_BACKUP": "WIB",
}

COMMISSION_TIERS = [
    ("5-9", 5, 9, "100.00", "75.00", "60.00", "50.00", "30.00"),
    ("10-14", 10, 14, "200.00", "150.00", "120.00", "100.00", "60.00"),
    ("15-19", 15, 19, "225.00", "175.00", "140.00", "120.00", "70.00"),
    ("20-24", 20, 24, "250.00", "200.00", "160.00", "140.00", "80.00"),
    ("25-29", 25, 29, "275.00", "225.00", "180.00", "160.00", "90.00"),
    ("30+", 30, None, "300.00", "250.00", "200.00", "180.00", "100.00"),
]


def seed_products(session: Session) -> int:
    created = 0
    for legacy_code, current_code in LEGACY_PRODUCT_CODES.items():
        legacy_product = session.scalar(select(Product).where(Product.code == legacy_code))
        current_product = session.scalar(select(Product).where(Product.code == current_code))
        if legacy_product is not None and current_product is None:
            legacy_product.code = current_code
        elif legacy_product is not None and current_product is not None:
            session.delete(legacy_product)
    session.flush()

    for product_data in PRODUCTS:
        existing_product = session.scalar(select(Product).where(Product.code == product_data["code"]))
        if existing_product is not None:
            for key, value in product_data.items():
                setattr(existing_product, key, value)
            continue

        defaults = {
            "active": True,
            "counts_as_internet_connect": False,
            "counts_as_connected_unit": False,
            "creates_mrr": False,
            "uses_tiered_rates": False,
            "uses_flat_rate": False,
            "available_new_customer": True,
            "available_existing_customer": True,
            "available_soho": False,
            "requires_existing_internet": False,
        }
        defaults.update(product_data)
        product = Product(**defaults)
        session.add(product)
        created += 1

    session.commit()
    return created


def seed_commission_plan(session: Session) -> tuple[bool, int]:
    plan = session.scalar(select(CommissionPlan).where(CommissionPlan.name == COMMISSION_PLAN_NAME))
    created_plan = False
    created_tiers = 0

    if plan is None:
        plan = CommissionPlan(
            name=COMMISSION_PLAN_NAME,
            effective_start=date(2026, 1, 1),
            active=True,
            bonus_percentage=Decimal("7.50"),
            bonus_unit_threshold=20,
            minimum_internet_threshold=5,
            notes="Development configuration for Spectrum Business AE 2026 compensation.",
        )
        session.add(plan)
        session.flush()
        created_plan = True

    existing_tier_names = {tier.tier_name for tier in plan.tiers}
    for display_order, tier_data in enumerate(COMMISSION_TIERS, start=1):
        tier_name, minimum, maximum, internet, mobile, voice, video, mrr = tier_data
        if tier_name in existing_tier_names:
            continue

        session.add(
            CommissionTier(
                commission_plan=plan,
                tier_name=tier_name,
                minimum_internet=minimum,
                maximum_internet=maximum,
                internet_rate=Decimal(internet),
                mobile_rate=Decimal(mobile),
                voice_rate=Decimal(voice),
                video_rate=Decimal(video),
                mrr_percentage=Decimal(mrr),
                display_order=display_order,
            )
        )
        created_tiers += 1

    session.commit()
    return created_plan, created_tiers


def seed_configuration(session: Session) -> tuple[int, bool, int]:
    products_created = seed_products(session)
    plan_created, tiers_created = seed_commission_plan(session)
    return products_created, plan_created, tiers_created


def seed_demo(session: Session) -> bool:
    existing_company = session.scalar(select(Company).where(Company.name == COMPANY_NAME))
    if existing_company is not None:
        print(f"Demo data already exists for {COMPANY_NAME}; no records created.")
        return False

    company = Company(
        name=COMPANY_NAME,
        main_phone="727-555-0198",
        industry="Plumbing services",
        estimated_employees=12,
        estimated_mobile_lines=8,
        status="prospect_review",
        notes="Development demo account for local MVP testing.",
    )

    commercial_location = Location(
        company=company,
        location_name="Spring Hill office",
        address_line_1="7421 Commercial Way",
        city="Spring Hill",
        state="FL",
        postal_code="34606",
        location_type=LocationType.COMMERCIAL,
        territory_status=TerritoryStatus.INSIDE,
        spectrum_relationship=SpectrumRelationship.EXISTING,
        business_use_confirmed=True,
        is_primary_business_location=True,
        current_provider_notes="Existing Spectrum Internet and Voice customer.",
    )

    home_location = Location(
        company=company,
        location_name="John Carter Home",
        address_line_1="1188 Waterfall Dr",
        city="Spring Hill",
        state="FL",
        postal_code="34608",
        location_type=LocationType.SOHO,
        territory_status=TerritoryStatus.INSIDE,
        spectrum_relationship=SpectrumRelationship.PROSPECT,
        business_use_confirmed=True,
        current_provider_notes="Owner uses competitor Internet at home.",
    )

    contact = Contact(
        company=company,
        location=commercial_location,
        first_name="John",
        last_name="Carter",
        job_title="Owner",
        phone="727-555-0142",
        email="john.carter@example.com",
        decision_role=ContactRole.DECISION_MAKER,
        preferred_contact_method="phone",
        is_primary_contact=True,
    )

    opportunity = Opportunity(
        company=company,
        location=commercial_location,
        primary_contact=contact,
        name="Sunshine Plumbing Account Review",
        stage=OpportunityStage.QUALIFIED,
        primary_product=ProductType.MOBILE,
        internet_probability=75,
        revenue_potential_score=82,
        cross_sell_score=88,
        priority_score=85,
        estimated_mobile_lines=8,
        estimated_voice_units=1,
        estimated_video_units=2,
        estimated_mrr=Decimal("649.97"),
        next_action="Call owner to review mobile pricing",
        next_action_date=date.today() + timedelta(days=1),
        score_reason="Existing customer with clear mobile, video, and voice gaps.",
    )

    services = [
        Service(
            company=company,
            location=commercial_location,
            contact=contact,
            opportunity=opportunity,
            record_type=ServiceRecordType.ACTIVE_SERVICE,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.INTERNET,
            service_status=ServiceStatus.ACTIVE,
            current_quantity=1,
            plan_name="Business Internet",
        ),
        Service(
            company=company,
            location=commercial_location,
            contact=contact,
            opportunity=opportunity,
            record_type=ServiceRecordType.ACTIVE_SERVICE,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.VOICE,
            service_status=ServiceStatus.ACTIVE,
            current_quantity=2,
            plan_name="Business Voice",
        ),
        Service(
            company=company,
            location=commercial_location,
            contact=contact,
            opportunity=opportunity,
            record_type=ServiceRecordType.PRODUCT_OPPORTUNITY,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.MOBILE,
            account_type="BUSINESS",
            potential_quantity=8,
            recommended_offer="Business mobile lines for field team.",
        ),
        Service(
            company=company,
            location=commercial_location,
            contact=contact,
            opportunity=opportunity,
            record_type=ServiceRecordType.PRODUCT_OPPORTUNITY,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.VIDEO,
            account_type="BUSINESS",
            potential_quantity=2,
            recommended_offer="Lobby and breakroom TV package.",
        ),
        Service(
            company=company,
            location=commercial_location,
            contact=contact,
            opportunity=opportunity,
            record_type=ServiceRecordType.PRODUCT_OPPORTUNITY,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.VOICE,
            account_type="BUSINESS",
            potential_quantity=1,
            recommended_offer="Additional office voice line.",
        ),
        Service(
            company=company,
            location=home_location,
            contact=contact,
            record_type=ServiceRecordType.ACTIVE_SERVICE,
            provider=ProviderType.COMPETITOR,
            product_type=ProductType.INTERNET,
            account_type="RESIDENTIAL",
            service_status=ServiceStatus.ACTIVE,
            current_quantity=1,
            source="Owner conversation",
        ),
        Service(
            company=company,
            location=home_location,
            contact=contact,
            record_type=ServiceRecordType.PRODUCT_OPPORTUNITY,
            provider=ProviderType.SPECTRUM,
            product_type=ProductType.INTERNET,
            account_type="SOHO",
            potential_quantity=1,
            recommended_offer="Spectrum SOHO Internet for owner home office.",
        ),
    ]

    activity = Activity(
        company=company,
        location=commercial_location,
        contact=contact,
        opportunity=opportunity,
        activity_type=ActivityType.DOOR_KNOCK,
        activity_at=datetime.now(UTC),
        outcome=ActivityOutcome.DECISION_MAKER_REACHED,
        disposition="Owner reached",
        products_discussed="Internet, Voice, Mobile, Video, SOHO Internet",
        notes="Initial door-knock visit. Owner was open to reviewing mobile pricing.",
        follow_up_required=True,
    )

    task = Task(
        company=company,
        location=commercial_location,
        contact=contact,
        opportunity=opportunity,
        task_type=TaskType.CALL,
        title="Call owner to review mobile pricing",
        due_at=datetime.now(UTC) + timedelta(days=1),
        priority="high",
        status=TaskStatus.OPEN,
        notes="Review eight mobile lines and possible SOHO Internet bundle.",
    )

    session.add_all([company, commercial_location, home_location, contact, opportunity, *services, activity, task])
    session.commit()
    print(f"Created demo data for {COMPANY_NAME}.")
    return True


def product_type_for_code(product_code: str) -> ProductType:
    product_types = {
        "BUSINESS_INTERNET": ProductType.INTERNET,
        "BUSINESS_MOBILE": ProductType.MOBILE,
        "BUSINESS_VOICE": ProductType.VOICE,
        "BUSINESS_VIDEO": ProductType.VIDEO,
        "WIB": ProductType.BACKUP_INTERNET,
        "INVINCIBLE_WIFI": ProductType.WIFI,
        "UNLIMITED_PLUS": ProductType.MOBILE,
    }
    return product_types[product_code]


def sale_item_for_product(product: Product, quantity: int, incremental_mrr: str) -> SaleItem:
    mrr = Decimal(incremental_mrr)
    return SaleItem(
        product=product,
        product_type=product_type_for_code(product.code),
        quantity=quantity,
        monthly_revenue=mrr,
        incremental_mrr=mrr,
    )


def seed_demo_sales(session: Session) -> bool:
    existing_demo_sale = session.scalar(select(Sale).where(Sale.notes == DEMO_SALES_MARKER))
    if existing_demo_sale is not None:
        print("Demo July 2026 sales already exist; no sales created.")
        return False

    company = session.scalar(select(Company).where(Company.name == COMPANY_NAME))
    if company is None:
        seed_demo(session)
        company = session.scalar(select(Company).where(Company.name == COMPANY_NAME))
    if company is None:
        raise RuntimeError(f"Could not find or create {COMPANY_NAME}.")

    location = company.locations[0]
    opportunity = company.opportunities[0] if company.opportunities else None
    products = {product.code: product for product in session.scalars(select(Product)).all()}
    required_codes = {
        "BUSINESS_INTERNET",
        "BUSINESS_MOBILE",
        "BUSINESS_VOICE",
        "BUSINESS_VIDEO",
        "WIB",
    }
    missing_codes = sorted(required_codes - set(products))
    if missing_codes:
        raise RuntimeError(f"Missing seeded products for demo sales: {', '.join(missing_codes)}.")

    sales = [
        Sale(
            opportunity=opportunity,
            company=company,
            location=location,
            order_date=date(2026, 7, 7),
            status=SaleStatus.INSTALLED,
            total_mrr=Decimal("900.00"),
            notes=DEMO_SALES_MARKER,
            sale_items=[
                sale_item_for_product(products["BUSINESS_INTERNET"], 3, "300.00"),
                sale_item_for_product(products["BUSINESS_MOBILE"], 8, "400.00"),
                sale_item_for_product(products["BUSINESS_VOICE"], 2, "100.00"),
                sale_item_for_product(products["BUSINESS_VIDEO"], 1, "100.00"),
            ],
        ),
        Sale(
            opportunity=opportunity,
            company=company,
            location=location,
            order_date=date(2026, 7, 18),
            status=SaleStatus.INSTALLED,
            total_mrr=Decimal("450.00"),
            notes=DEMO_SALES_MARKER,
            sale_items=[
                sale_item_for_product(products["BUSINESS_INTERNET"], 2, "250.00"),
                sale_item_for_product(products["BUSINESS_MOBILE"], 4, "100.00"),
                sale_item_for_product(products["WIB"], 1, "100.00"),
            ],
        ),
        Sale(
            opportunity=opportunity,
            company=company,
            location=location,
            order_date=date(2026, 7, 20),
            status=SaleStatus.SUBMITTED,
            total_mrr=Decimal("700.00"),
            notes=DEMO_SALES_MARKER,
            sale_items=[
                sale_item_for_product(products["BUSINESS_INTERNET"], 2, "300.00"),
                sale_item_for_product(products["BUSINESS_MOBILE"], 10, "400.00"),
            ],
        ),
        Sale(
            opportunity=opportunity,
            company=company,
            location=location,
            order_date=date(2026, 7, 22),
            status=SaleStatus.CANCELED,
            total_mrr=Decimal("150.00"),
            notes=DEMO_SALES_MARKER,
            sale_items=[sale_item_for_product(products["BUSINESS_INTERNET"], 1, "150.00")],
        ),
    ]

    session.add_all(sales)
    session.commit()
    print("Created July 2026 demo sales.")
    return True


def print_demo_summary(session: Session) -> None:
    company = session.scalar(select(Company).where(Company.name == COMPANY_NAME))
    if company is None:
        print(f"No demo company found for {COMPANY_NAME}.")
        return

    print(f"Company: {company.name}")
    print("Locations:")
    for location in company.locations:
        print(f"  - {location.location_name}: {location.address_line_1}, {location.city}, {location.state}")

    active_services = [
        service for service in company.services if service.record_type == ServiceRecordType.ACTIVE_SERVICE
    ]
    product_opportunities = [
        service for service in company.services if service.record_type == ServiceRecordType.PRODUCT_OPPORTUNITY
    ]

    print("Active services:")
    for service in active_services:
        print(f"  - {service.provider.value} {service.product_type.value}: quantity {service.current_quantity}")

    print("Product opportunities:")
    for service in product_opportunities:
        print(f"  - {service.provider.value} {service.product_type.value}: potential {service.potential_quantity}")

    print("Activities:")
    for activity in company.activities:
        print(f"  - {activity.activity_type.value}: {activity.outcome.value if activity.outcome else 'UNKNOWN'}")

    print("Tasks:")
    for task in company.tasks:
        print(f"  - {task.title}: {task.status.value}")

    print("Sales:")
    sales = session.scalars(select(Sale).where(Sale.company_id == company.id)).all()
    if not sales:
        print("  - none")
    for sale in sales:
        print(f"  - Sale {sale.id}: {sale.status.value}")


def print_configuration_summary(session: Session) -> None:
    product_count = session.scalar(select(func.count()).select_from(Product))
    plan_count = session.scalar(select(func.count()).select_from(CommissionPlan))
    tier_count = session.scalar(select(func.count()).select_from(CommissionTier))

    print(f"Number of products: {product_count}")
    print(f"Number of commission plans: {plan_count}")
    print(f"Number of commission tiers: {tier_count}")
    sale_count = session.scalar(select(func.count()).select_from(Sale).where(Sale.notes == DEMO_SALES_MARKER))
    print(f"Number of July 2026 demo sales: {sale_count}")


if __name__ == "__main__":
    from app.init_db import init_db

    init_db()
    with SessionLocal() as session:
        products_created, plan_created, tiers_created = seed_configuration(session)
        print(f"Products created: {products_created}")
        print(f"Commission plan created: {plan_created}")
        print(f"Commission tiers created: {tiers_created}")
        seed_demo(session)
        seed_demo_sales(session)
        print_demo_summary(session)
        print_configuration_summary(session)
