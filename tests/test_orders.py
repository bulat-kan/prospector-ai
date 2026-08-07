from datetime import date, datetime, UTC
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from app.analytics import calculate_monthly_commission
from app.audit_data import audit_orders
from app.crud import RecordNotFoundError
from app.enums import LocationType, OpportunityStage, ProductType, SaleStatus
from app.models import Company, Contact, Location, Opportunity, OpportunityProduct, Product, Sale, SaleItem
from app.order_service import (
    CreatedOrderResult,
    DuplicateOrderItemError,
    OrderItemInput,
    OrderValidationError,
    add_order_item,
    build_order_preview_from_opportunity,
    create_order_from_opportunity,
    create_order_with_items,
    get_order,
    is_order_canceled,
    is_order_legacy_commission_eligible,
    is_order_open,
    list_order_items,
    list_orders,
    normalize_order_status,
    order_status_display,
    remove_order_item,
    update_order,
    update_order_item,
)
from app.seed_demo import seed_configuration, seed_demo, seed_demo_sales


def seed_products(db_session) -> dict[str, Product]:
    seed_configuration(db_session)
    return {product.code: product for product in db_session.scalars(select(Product)).all()}


def create_company(db_session, *, name: str = "Order Test LLC", active: bool = True) -> Company:
    company = Company(name=name, is_active=active)
    db_session.add(company)
    db_session.commit()
    return company


def create_location(db_session, company: Company, *, active: bool = True, name: str = "Main Office") -> Location:
    location = Location(
        company=company,
        location_name=name,
        address_line_1=f"{name} 100 Main St",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.SMB,
        is_active=active,
    )
    db_session.add(location)
    db_session.commit()
    return location


def create_contact(db_session, company: Company, *, active: bool = True) -> Contact:
    contact = Contact(company=company, first_name="Jordan", last_name="Smith", is_active=active)
    db_session.add(contact)
    db_session.commit()
    return contact


def create_opportunity_with_products(db_session, company: Company, products: dict[str, Product]) -> Opportunity:
    opportunity = Opportunity(
        company=company,
        name="Account Review",
        stage=OpportunityStage.QUALIFIED,
        next_action="Call",
        next_action_date=date(2026, 7, 10),
        products=[
            OpportunityProduct(
                product=products["BUSINESS_INTERNET"],
                product_code="BUSINESS_INTERNET",
                estimated_quantity=3,
                estimated_incremental_mrr=Decimal("300.00"),
                notes="Estimated internet",
            ),
            OpportunityProduct(
                product=products["BUSINESS_MOBILE"],
                product_code="BUSINESS_MOBILE",
                estimated_quantity=8,
                estimated_incremental_mrr=Decimal("400.00"),
            ),
        ],
    )
    db_session.add(opportunity)
    db_session.commit()
    return opportunity


def item(code: str, quantity: int = 1, mrr: str = "0.00") -> OrderItemInput:
    return OrderItemInput(product_code=code, quantity=quantity, incremental_mrr=Decimal(mrr))


@pytest.mark.parametrize(
    "status",
    [
        SaleStatus.DRAFT,
        SaleStatus.SUBMITTED,
        SaleStatus.SCHEDULED,
        SaleStatus.PARTIALLY_FULFILLED,
        SaleStatus.FULFILLED,
        SaleStatus.CANCELED,
    ],
)
def test_order_statuses_are_accepted(status: SaleStatus) -> None:
    assert normalize_order_status(status) == status


def test_legacy_installed_remains_readable_and_labels_work() -> None:
    assert normalize_order_status("INSTALLED") == SaleStatus.INSTALLED
    assert normalize_order_status("CANCELLED") == SaleStatus.CANCELED
    assert order_status_display(SaleStatus.DRAFT) == "Draft"
    assert order_status_display(SaleStatus.PARTIALLY_FULFILLED) == "Partially Fulfilled"
    assert order_status_display(SaleStatus.INSTALLED) == "Installed (Legacy)"
    assert is_order_open(SaleStatus.SUBMITTED)
    assert is_order_canceled("CANCELLED")
    assert is_order_legacy_commission_eligible(SaleStatus.INSTALLED)


def test_invalid_status_rejected() -> None:
    with pytest.raises(OrderValidationError, match="Unsupported order status"):
        normalize_order_status("NOT_A_STATUS")


def test_create_order_for_active_company_with_location_contact_and_opportunity(db_session) -> None:
    products = seed_products(db_session)
    company = create_company(db_session)
    location = create_location(db_session, company)
    contact = create_contact(db_session, company)
    opportunity = create_opportunity_with_products(db_session, company, products)

    created = create_order_with_items(
        db_session,
        company_id=company.id,
        location_id=location.id,
        contact_id=contact.id,
        opportunity_id=opportunity.id,
        order_date=date(2026, 8, 1),
        status=SaleStatus.SUBMITTED,
        external_order_number="SO-1001",
        customer_account_reference="ACCT-77",
        submitted_at=datetime(2026, 8, 1, 14, 30, tzinfo=UTC),
        items=[item("BUSINESS_INTERNET", 1, "100.00")],
    )
    detail = get_order(db_session, created.order_id)

    assert created.company_name == company.name
    assert created.opportunity_name == opportunity.name
    assert created.item_count == 1
    assert detail.summary.location_name == "Main Office"
    assert detail.summary.contact_name == "Jordan Smith"
    assert detail.customer_account_reference == "ACCT-77"


def test_create_order_rejects_inactive_and_cross_company_relationships(db_session) -> None:
    seed_products(db_session)
    inactive_company = create_company(db_session, active=False)
    with pytest.raises(OrderValidationError, match="inactive"):
        create_order_with_items(
            db_session,
            company_id=inactive_company.id,
            order_date=date(2026, 8, 1),
            items=[item("BUSINESS_INTERNET")],
        )

    company = create_company(db_session, name="Active Order Company")
    other = create_company(db_session, name="Other Order Company")
    inactive_location = create_location(db_session, company, active=False)
    inactive_contact = create_contact(db_session, company, active=False)
    other_location = create_location(db_session, other)
    other_contact = create_contact(db_session, other)
    other_opportunity = create_opportunity_with_products(db_session, other, seed_products(db_session))

    with pytest.raises(OrderValidationError, match="Location"):
        create_order_with_items(db_session, company_id=company.id, location_id=inactive_location.id, order_date=date(2026, 8, 1), items=[item("BUSINESS_INTERNET")])
    with pytest.raises(OrderValidationError, match="Contact"):
        create_order_with_items(db_session, company_id=company.id, contact_id=inactive_contact.id, order_date=date(2026, 8, 1), items=[item("BUSINESS_INTERNET")])
    with pytest.raises(OrderValidationError, match="location does not belong"):
        create_order_with_items(db_session, company_id=company.id, location_id=other_location.id, order_date=date(2026, 8, 1), items=[item("BUSINESS_INTERNET")])
    with pytest.raises(OrderValidationError, match="contact does not belong"):
        create_order_with_items(db_session, company_id=company.id, contact_id=other_contact.id, order_date=date(2026, 8, 1), items=[item("BUSINESS_INTERNET")])
    with pytest.raises(OrderValidationError, match="opportunity does not belong"):
        create_order_with_items(db_session, company_id=company.id, opportunity_id=other_opportunity.id, order_date=date(2026, 8, 1), items=[item("BUSINESS_INTERNET")])


def test_required_order_date_and_items(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session)
    with pytest.raises(OrderValidationError, match="Order date is required"):
        create_order_with_items(db_session, company_id=company.id, order_date=None, items=[item("BUSINESS_INTERNET")])
    with pytest.raises(OrderValidationError, match="Select at least one product"):
        create_order_with_items(db_session, company_id=company.id, order_date=date(2026, 8, 1), items=[])


def test_order_items_validation_and_atomic_rollback(db_session) -> None:
    products = seed_products(db_session)
    company = create_company(db_session)
    products["SECURITY"].active = False
    db_session.commit()
    before_sales = db_session.scalar(select(func.count()).select_from(Sale))
    before_items = db_session.scalar(select(func.count()).select_from(SaleItem))

    valid = create_order_with_items(
        db_session,
        company_id=company.id,
        order_date=date(2026, 8, 1),
        items=[item("BUSINESS_INTERNET", 1, "100.123"), item("BUSINESS_MOBILE", 4, "200.00")],
    )
    assert valid.item_count == 2
    assert valid.total_quantity == 5
    assert valid.total_incremental_mrr == Decimal("300.12")

    invalid_cases = [
        (OrderItemInput(product_code="BUSINESS_INTERNET", quantity=0), "greater than zero"),
        (OrderItemInput(product_code="BUSINESS_INTERNET", quantity=-1), "greater than zero"),
        (OrderItemInput(product_code="BUSINESS_INTERNET", quantity=1, incremental_mrr=Decimal("-1.00")), "MRR"),
        (OrderItemInput(product_code="SECURITY", quantity=1), "Inactive products"),
    ]
    for invalid_item, message in invalid_cases:
        with pytest.raises(OrderValidationError, match=message):
            create_order_with_items(db_session, company_id=company.id, order_date=date(2026, 8, 2), items=[invalid_item])

    with pytest.raises(RecordNotFoundError):
        create_order_with_items(db_session, company_id=company.id, order_date=date(2026, 8, 2), items=[item("NOPE")])
    with pytest.raises(DuplicateOrderItemError):
        create_order_with_items(
            db_session,
            company_id=company.id,
            order_date=date(2026, 8, 2),
            items=[item("BUSINESS_INTERNET"), item("BUSINESS_INTERNET")],
        )

    assert db_session.scalar(select(func.count()).select_from(Sale)) == before_sales + 1
    assert db_session.scalar(select(func.count()).select_from(SaleItem)) == before_items + 2


def test_order_preview_from_opportunity_is_detached_safe_and_read_only(db_session) -> None:
    products = seed_products(db_session)
    company = create_company(db_session, name="Preview Company")
    location = create_location(db_session, company)
    contact = create_contact(db_session, company)
    opportunity = create_opportunity_with_products(db_session, company, products)
    opportunity.location = location
    opportunity.primary_contact = contact
    db_session.commit()
    original_stage = opportunity.stage

    preview = build_order_preview_from_opportunity(db_session, opportunity.id)
    db_session.expunge_all()

    assert preview.opportunity_name == "Account Review"
    assert preview.company_name == "Preview Company"
    assert preview.location_name == "Main Office"
    assert preview.primary_contact_name == "Jordan Smith"
    assert {row.product_code for row in preview.suggested_items} == {"BUSINESS_INTERNET", "BUSINESS_MOBILE"}
    assert preview.estimated_total_quantity == 11
    with db_session.bind.connect() as connection:
        stage = connection.execute(text("SELECT stage FROM opportunities WHERE id = :id"), {"id": preview.opportunity_id}).scalar_one()
    assert stage == original_stage.value


def test_create_order_from_opportunity_allows_actuals_to_differ_and_multiple_orders(db_session) -> None:
    products = seed_products(db_session)
    company = create_company(db_session)
    opportunity = create_opportunity_with_products(db_session, company, products)

    first = create_order_from_opportunity(
        db_session,
        opportunity_id=opportunity.id,
        order_date=date(2026, 8, 1),
        status=SaleStatus.SUBMITTED,
        item_inputs=[item("BUSINESS_INTERNET", 1, "125.00"), item("BUSINESS_VOICE", 2, "80.00")],
    )
    second = create_order_from_opportunity(
        db_session,
        opportunity_id=opportunity.id,
        order_date=date(2026, 8, 5),
        status=SaleStatus.DRAFT,
        item_inputs=[item("BUSINESS_MOBILE", 4, "100.00")],
    )
    loaded_opportunity = db_session.get(Opportunity, opportunity.id)

    assert first.total_quantity == 3
    assert second.total_quantity == 4
    assert len(list_orders(db_session, opportunity_id=opportunity.id)) == 2
    assert loaded_opportunity.stage == OpportunityStage.QUALIFIED


def test_closed_won_does_not_automatically_create_order(db_session) -> None:
    products = seed_products(db_session)
    company = create_company(db_session)
    opportunity = create_opportunity_with_products(db_session, company, products)
    opportunity.stage = OpportunityStage.CLOSED_WON
    db_session.commit()

    build_order_preview_from_opportunity(db_session, opportunity.id)

    assert list_orders(db_session, opportunity_id=opportunity.id) == ()


def test_created_order_result_has_no_orm_dependency_after_detach(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session, name="Detached Order Company")
    opportunity = create_opportunity_with_products(db_session, company, seed_products(db_session))

    created = create_order_with_items(
        db_session,
        company_id=company.id,
        opportunity_id=opportunity.id,
        order_date=date(2026, 8, 1),
        items=[item("BUSINESS_INTERNET", 1, "100.00")],
    )
    db_session.expunge_all()

    assert isinstance(created, CreatedOrderResult)
    assert created.company_name == "Detached Order Company"
    assert created.opportunity_name == "Account Review"
    assert created.order_id > 0
    assert not hasattr(created, "_sa_instance_state")


def test_update_order_and_items(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session)
    location = create_location(db_session, company)
    contact = create_contact(db_session, company)
    created = create_order_with_items(
        db_session,
        company_id=company.id,
        order_date=date(2026, 8, 1),
        items=[item("BUSINESS_INTERNET", 1, "100.00")],
    )

    updated = update_order(
        db_session,
        created.order_id,
        status=SaleStatus.SCHEDULED,
        location_id=location.id,
        contact_id=contact.id,
        external_order_number="SO-2002",
        notes="Updated",
    )
    added = add_order_item(db_session, created.order_id, item("BUSINESS_MOBILE", 4, "200.00"))
    changed = update_order_item(db_session, added.id, quantity=5, incremental_mrr=Decimal("250.00"), notes="Corrected")
    remove_order_item(db_session, changed.id)

    assert updated.summary.status == SaleStatus.SCHEDULED
    assert updated.summary.location_id == location.id
    assert updated.summary.contact_id == contact.id
    assert list_order_items(db_session, created.order_id)[0].product_code == "BUSINESS_INTERNET"
    with pytest.raises(OrderValidationError, match="Company cannot be changed"):
        update_order(db_session, created.order_id, company_id=999)
    with pytest.raises(OrderValidationError, match="Opportunity source cannot be changed"):
        update_order(db_session, created.order_id, opportunity_id=999)


def test_listing_filters_ordering_and_summary_values(db_session) -> None:
    seed_products(db_session)
    company = create_company(db_session, name="List Company")
    other = create_company(db_session, name="Other List Company")
    opportunity = create_opportunity_with_products(db_session, company, seed_products(db_session))
    older = create_order_with_items(
        db_session,
        company_id=company.id,
        opportunity_id=opportunity.id,
        order_date=date(2026, 8, 1),
        status=SaleStatus.DRAFT,
        external_order_number="SO-OLD",
        items=[item("BUSINESS_INTERNET", 1, "100.00")],
    )
    newer = create_order_with_items(
        db_session,
        company_id=company.id,
        opportunity_id=opportunity.id,
        order_date=date(2026, 8, 3),
        status=SaleStatus.SUBMITTED,
        external_order_number="SO-NEW",
        items=[item("BUSINESS_MOBILE", 4, "200.00")],
    )
    create_order_with_items(db_session, company_id=other.id, order_date=date(2026, 8, 2), items=[item("BUSINESS_VOICE", 1)])

    rows = list_orders(db_session, company_id=company.id)

    assert [row.order_id for row in rows] == [newer.order_id, older.order_id]
    assert list_orders(db_session, status=SaleStatus.SUBMITTED)[0].order_id == newer.order_id
    assert {
        row.order_id
        for row in list_orders(
            db_session,
            company_id=company.id,
            order_date_start=date(2026, 8, 2),
            order_date_end=date(2026, 8, 3),
        )
    } == {newer.order_id}
    assert list_orders(db_session, product_code="BUSINESS_INTERNET")[0].order_id == older.order_id
    assert len(list_orders(db_session, opportunity_id=opportunity.id)) == 2
    assert list_orders(db_session, external_order_number="NEW")[0].status_display == "Submitted"
    assert rows[0].product_names == ("Business Mobile",)
    assert rows[0].total_quantity == 4
    assert rows[0].total_incremental_mrr == Decimal("200.00")


def test_nonfulfilled_orders_and_closed_won_opportunity_do_not_affect_commission(db_session) -> None:
    seed_configuration(db_session)
    seed_demo(db_session)
    seed_demo_sales(db_session)
    company = db_session.scalar(select(Company).where(Company.name == "Sunshine Plumbing LLC"))
    opportunity = company.opportunities[0]
    opportunity.stage = OpportunityStage.CLOSED_WON
    create_order_with_items(
        db_session,
        company_id=company.id,
        opportunity_id=opportunity.id,
        order_date=date(2026, 7, 9),
        status=SaleStatus.DRAFT,
        items=[item("BUSINESS_INTERNET", 10, "1000.00")],
    )
    create_order_with_items(
        db_session,
        company_id=company.id,
        opportunity_id=opportunity.id,
        order_date=date(2026, 7, 10),
        status=SaleStatus.SUBMITTED,
        items=[item("BUSINESS_MOBILE", 10, "500.00")],
    )
    create_order_with_items(
        db_session,
        company_id=company.id,
        opportunity_id=opportunity.id,
        order_date=date(2026, 7, 11),
        status=SaleStatus.SCHEDULED,
        items=[item("BUSINESS_VOICE", 10, "500.00")],
    )

    analytics = calculate_monthly_commission(db_session, 2026, 7)

    assert analytics.sales_summary.eligible_sale_count == 2
    assert analytics.commission_result.estimated_payout == Decimal("2200.25")


def test_audit_detects_order_issues_and_is_read_only(db_session) -> None:
    products = seed_products(db_session)
    company = create_company(db_session)
    other = create_company(db_session, name="Audit Other")
    bad_location = create_location(db_session, other)
    order = Sale(
        company=company,
        location=bad_location,
        order_date=date(2026, 8, 1),
        status=SaleStatus.SUBMITTED,
        sale_items=[
            SaleItem(product=products["BUSINESS_INTERNET"], product_type=ProductType.INTERNET, quantity=1),
            SaleItem(product=products["BUSINESS_INTERNET"], product_type=ProductType.INTERNET, quantity=2),
            SaleItem(product_type=ProductType.MOBILE, quantity=0, incremental_mrr=Decimal("-1.00")),
        ],
    )
    empty_order = Sale(company=company, order_date=date(2026, 8, 2), status=SaleStatus.DRAFT)
    db_session.add_all([order, empty_order])
    db_session.commit()
    before = db_session.scalar(select(func.count()).select_from(Sale))

    issues = audit_orders(db_session)
    after = db_session.scalar(select(func.count()).select_from(Sale))

    messages = [issue.message for issue in issues]
    assert any("location belongs to another company" in message for message in messages)
    assert any("no order items" in message for message in messages)
    assert any("missing product" in message for message in messages)
    assert any("quantity must be greater than zero" in message for message in messages)
    assert any("negative incremental MRR" in message for message in messages)
    assert any("duplicate product rows" in message for message in messages)
    assert before == after


def test_seed_and_init_style_workflows_remain_clean(db_session) -> None:
    seed_configuration(db_session)
    seed_demo(db_session)
    seed_demo_sales(db_session)

    assert not audit_orders(db_session)
    assert db_session.scalar(select(func.count()).select_from(Sale)) == 4
