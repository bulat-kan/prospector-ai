from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.analytics import (
    InvalidSaleItemError,
    MissingProductReferenceError,
    build_monthly_commission_input,
    calculate_monthly_commission,
    forecast_internet_target,
    forecast_next_tier,
    money,
)
from app.enums import LocationType, ProductType, SaleStatus
from app.models import Company, Location, Product, Sale, SaleItem
from app.seed_demo import DEMO_SALES_MARKER, product_type_for_code, seed_configuration, seed_demo, seed_demo_sales


@pytest.fixture
def seeded_session(db_session):
    seed_configuration(db_session)
    return db_session


@pytest.fixture
def company_and_location(seeded_session):
    company = Company(name="Analytics Test LLC")
    location = Location(
        company=company,
        address_line_1="100 Analytics Way",
        city="Spring Hill",
        state="FL",
        postal_code="34609",
        location_type=LocationType.COMMERCIAL,
    )
    seeded_session.add_all([company, location])
    seeded_session.commit()
    return company, location


def product(seeded_session, code: str) -> Product:
    found = seeded_session.scalar(select(Product).where(Product.code == code))
    assert found is not None
    return found


def sale_item(seeded_session, code: str, quantity: int, mrr: str = "0.00") -> SaleItem:
    found = product(seeded_session, code)
    value = Decimal(mrr)
    return SaleItem(
        product=found,
        product_type=product_type_for_code(code),
        quantity=quantity,
        monthly_revenue=value,
        incremental_mrr=value,
    )


def add_sale(
    seeded_session,
    company_and_location,
    *,
    order_date: date,
    status: SaleStatus = SaleStatus.INSTALLED,
    items: list[SaleItem],
) -> Sale:
    company, location = company_and_location
    sale = Sale(
        company=company,
        location=location,
        order_date=order_date,
        status=status,
        sale_items=items,
    )
    seeded_session.add(sale)
    seeded_session.commit()
    return sale


def totals_by_code(summary):
    return {total.product_code: total for total in summary.product_totals}


def test_empty_month(seeded_session) -> None:
    commission_input, summary = build_monthly_commission_input(seeded_session, 2026, 7)
    analytics = calculate_monthly_commission(seeded_session, 2026, 7)

    assert commission_input.internet_connects == 0
    assert commission_input.lines == ()
    assert summary.eligible_sale_count == 0
    assert summary.product_totals == ()
    assert summary.internet_connects == 0
    assert summary.total_incremental_mrr == Decimal("0.00")
    assert analytics.commission_result.estimated_payout == Decimal("0.00")


def test_connected_sales_count(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 1)],
    )
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 2),
        status=SaleStatus.SUBMITTED,
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 1)],
    )

    _, summary = build_monthly_commission_input(seeded_session, 2026, 7)

    assert summary.eligible_sale_count == 1


def test_excluded_sales_count(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 2),
        status=SaleStatus.SUBMITTED,
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 1)],
    )
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 3),
        status=SaleStatus.CANCELED,
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 1)],
    )

    _, summary = build_monthly_commission_input(seeded_session, 2026, 7)

    assert summary.excluded_sale_count == 2


def test_date_boundaries_and_december_rollover(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 1)],
    )
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 31),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 1)],
    )
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 8, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 1)],
    )
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 12, 31),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 1)],
    )
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2027, 1, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 1)],
    )

    _, july = build_monthly_commission_input(seeded_session, 2026, 7)
    _, december = build_monthly_commission_input(seeded_session, 2026, 12)

    assert july.eligible_sale_count == 2
    assert july.internet_connects == 2
    assert december.start_date == date(2026, 12, 1)
    assert december.end_date == date(2027, 1, 1)
    assert december.eligible_sale_count == 1


def test_product_grouping(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_MOBILE", 2, "20.00")],
    )
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 2),
        items=[sale_item(seeded_session, "BUSINESS_MOBILE", 3, "30.00")],
    )

    _, summary = build_monthly_commission_input(seeded_session, 2026, 7)
    mobile = totals_by_code(summary)["BUSINESS_MOBILE"]

    assert mobile.quantity == 5
    assert mobile.incremental_mrr == Decimal("50.00")


def test_internet_connects_derived_from_product_configuration(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 3), sale_item(seeded_session, "BUSINESS_MOBILE", 8)],
    )

    _, summary = build_monthly_commission_input(seeded_session, 2026, 7)

    assert summary.internet_connects == 3


def test_connected_units_derived_from_product_configuration(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 3), sale_item(seeded_session, "WIB", 2)],
    )

    _, summary = build_monthly_commission_input(seeded_session, 2026, 7)

    assert summary.connected_units == 3


def test_mrr_grouped_and_totaled_correctly(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[
            sale_item(seeded_session, "BUSINESS_INTERNET", 1, "100.25"),
            sale_item(seeded_session, "BUSINESS_MOBILE", 2, "50.50"),
        ],
    )

    _, summary = build_monthly_commission_input(seeded_session, 2026, 7)

    assert totals_by_code(summary)["BUSINESS_INTERNET"].incremental_mrr == Decimal("100.25")
    assert summary.total_incremental_mrr == Decimal("150.75")


def test_missing_product_id_strict_mode_raises(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[SaleItem(product_type=ProductType.INTERNET, quantity=1, incremental_mrr=Decimal("100.00"))],
    )

    with pytest.raises(MissingProductReferenceError, match="has no product_id"):
        build_monthly_commission_input(seeded_session, 2026, 7)


def test_negative_quantity_raises(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", -1)],
    )

    with pytest.raises(InvalidSaleItemError, match="negative quantity"):
        build_monthly_commission_input(seeded_session, 2026, 7)


def test_negative_mrr_raises(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 1, "-1.00")],
    )

    with pytest.raises(InvalidSaleItemError, match="negative incremental MRR"):
        build_monthly_commission_input(seeded_session, 2026, 7)


def test_zero_quantity_is_ignored(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 0, "100.00")],
    )

    _, summary = build_monthly_commission_input(seeded_session, 2026, 7)

    assert summary.product_totals == ()
    assert summary.total_incremental_mrr == Decimal("0.00")


def test_monthly_calculation_reuses_commission_engine(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[
            sale_item(seeded_session, "BUSINESS_INTERNET", 5, "500.00"),
            sale_item(seeded_session, "BUSINESS_MOBILE", 15, "500.00"),
        ],
    )

    analytics = calculate_monthly_commission(seeded_session, 2026, 7)

    assert analytics.commission_result.tier_name == "5-9"
    assert analytics.commission_result.bonus_eligible is True
    assert analytics.commission_result.estimated_payout == Decimal("2046.88")


def test_forecast_next_tier_does_not_mutate_current_input(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 9), sale_item(seeded_session, "BUSINESS_MOBILE", 20)],
    )
    current_input, _ = build_monthly_commission_input(seeded_session, 2026, 7)

    forecast = forecast_next_tier(seeded_session, 2026, 7)
    after_input, _ = build_monthly_commission_input(seeded_session, 2026, 7)

    assert forecast is not None
    assert current_input == after_input
    assert forecast.additional_internet_needed == 1
    assert forecast.projected_result.estimated_payout > forecast.current.commission_result.estimated_payout


def test_forecast_highest_tier_returns_none(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 30)],
    )

    assert forecast_next_tier(seeded_session, 2026, 7) is None


def test_target_lower_than_current_raises(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 5)],
    )

    with pytest.raises(ValueError, match="cannot be lower"):
        forecast_internet_target(seeded_session, 2026, 7, 4)


def test_product_configuration_remains_source_of_truth(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "WIB", 2)],
    )
    _, before = build_monthly_commission_input(seeded_session, 2026, 7)

    wib = product(seeded_session, "WIB")
    wib.counts_as_connected_unit = True
    seeded_session.commit()
    _, after = build_monthly_commission_input(seeded_session, 2026, 7)

    assert before.connected_units == 0
    assert after.connected_units == 2


def test_decimal_outputs_have_two_places(seeded_session, company_and_location) -> None:
    add_sale(
        seeded_session,
        company_and_location,
        order_date=date(2026, 7, 1),
        items=[sale_item(seeded_session, "BUSINESS_INTERNET", 5, "100.333")],
    )

    analytics = calculate_monthly_commission(seeded_session, 2026, 7)
    amounts = [
        analytics.sales_summary.total_incremental_mrr,
        analytics.commission_result.total_incremental_mrr,
        analytics.commission_result.mrr_payout,
        analytics.commission_result.estimated_payout,
    ]

    assert all(amount == money(amount) for amount in amounts)


def test_seed_demo_sales_is_idempotent(seeded_session) -> None:
    seed_demo(seeded_session)
    first = seed_demo_sales(seeded_session)
    second = seed_demo_sales(seeded_session)
    sale_count = seeded_session.scalar(select(func.count()).select_from(Sale).where(Sale.notes == DEMO_SALES_MARKER))

    assert first is True
    assert second is False
    assert sale_count == 4
