from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.commission import CommissionInput, CommissionLineInput, CommissionResult, calculate_commission, money
from app.database import SessionLocal
from app.enums import SaleStatus
from app.models import Product, Sale, SaleItem


ZERO = Decimal("0.00")
BUSINESS_INTERNET_CODE = "BUSINESS_INTERNET"


class AnalyticsError(Exception):
    """Base error for monthly sales analytics failures."""


class MissingProductReferenceError(AnalyticsError):
    """Raised when a sale item cannot be tied to a configured product."""


class InvalidSaleItemError(AnalyticsError):
    """Raised when a sale item has invalid quantity or MRR data."""


@dataclass(frozen=True)
class MonthlyProductTotal:
    product_code: str
    quantity: int
    incremental_mrr: Decimal


@dataclass(frozen=True)
class MonthlySalesSummary:
    year: int
    month: int
    start_date: date
    end_date: date
    eligible_sale_count: int
    excluded_sale_count: int
    product_totals: tuple[MonthlyProductTotal, ...]
    internet_connects: int
    connected_units: int
    total_incremental_mrr: Decimal


@dataclass(frozen=True)
class MonthlyCommissionAnalytics:
    sales_summary: MonthlySalesSummary
    commission_result: CommissionResult


@dataclass(frozen=True)
class CommissionForecast:
    current: MonthlyCommissionAnalytics
    target_internet_connects: int
    additional_internet_needed: int
    projected_result: CommissionResult
    payout_increase: Decimal


def is_sale_commission_eligible(sale: Sale) -> bool:
    return sale.status == SaleStatus.INSTALLED


def month_bounds(year: int, month: int) -> tuple[date, date]:
    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12.")
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    return start_date, end_date


def last_day_of_month(year: int, month: int) -> date:
    _, end_date = month_bounds(year, month)
    return end_date - timedelta(days=1)


def sale_item_mrr(sale_item: SaleItem) -> Decimal:
    value = sale_item.incremental_mrr
    if value is None:
        value = sale_item.monthly_revenue
    return money(value or ZERO)


def validate_sale_item(sale_item: SaleItem, strict: bool) -> Optional[Product]:
    if sale_item.product is None:
        if strict:
            raise MissingProductReferenceError(
                f"SaleItem id={sale_item.id!r} on sale_id={sale_item.sale_id!r} has no product_id."
            )
        return None
    if sale_item.quantity < 0:
        raise InvalidSaleItemError(f"SaleItem id={sale_item.id!r} has negative quantity {sale_item.quantity}.")
    incremental_mrr = sale_item_mrr(sale_item)
    if incremental_mrr < ZERO:
        raise InvalidSaleItemError(f"SaleItem id={sale_item.id!r} has negative incremental MRR {incremental_mrr}.")
    return sale_item.product


def build_monthly_commission_input(
    session: Session,
    year: int,
    month: int,
    strict: bool = True,
) -> tuple[CommissionInput, MonthlySalesSummary]:
    start_date, end_date = month_bounds(year, month)
    sales = session.scalars(
        select(Sale)
        .options(selectinload(Sale.sale_items).selectinload(SaleItem.product))
        .where(Sale.order_date >= start_date, Sale.order_date < end_date)
        .order_by(Sale.order_date, Sale.id)
    ).all()

    eligible_sales = [sale for sale in sales if is_sale_commission_eligible(sale)]
    excluded_sale_count = len(sales) - len(eligible_sales)
    grouped: dict[str, MonthlyProductTotal] = {}
    products_by_code: dict[str, Product] = {}

    for sale in eligible_sales:
        for sale_item in sale.sale_items:
            product = validate_sale_item(sale_item, strict)
            if product is None or sale_item.quantity == 0:
                continue

            incremental_mrr = sale_item_mrr(sale_item)
            existing_total = grouped.get(product.code)
            if existing_total is None:
                grouped[product.code] = MonthlyProductTotal(product.code, sale_item.quantity, incremental_mrr)
            else:
                grouped[product.code] = MonthlyProductTotal(
                    product_code=product.code,
                    quantity=existing_total.quantity + sale_item.quantity,
                    incremental_mrr=money(existing_total.incremental_mrr + incremental_mrr),
                )
            products_by_code[product.code] = product

    product_totals = tuple(grouped[code] for code in sorted(grouped))
    internet_connects = sum(
        total.quantity for total in product_totals if products_by_code[total.product_code].counts_as_internet_connect
    )
    connected_units = sum(
        total.quantity for total in product_totals if products_by_code[total.product_code].counts_as_connected_unit
    )
    total_incremental_mrr = money(sum((total.incremental_mrr for total in product_totals), ZERO))
    commission_input = CommissionInput(
        internet_connects=internet_connects,
        lines=tuple(
            CommissionLineInput(
                product_code=total.product_code,
                quantity=total.quantity,
                incremental_mrr=total.incremental_mrr,
            )
            for total in product_totals
        ),
    )
    summary = MonthlySalesSummary(
        year=year,
        month=month,
        start_date=start_date,
        end_date=end_date,
        eligible_sale_count=len(eligible_sales),
        excluded_sale_count=excluded_sale_count,
        product_totals=product_totals,
        internet_connects=internet_connects,
        connected_units=connected_units,
        total_incremental_mrr=total_incremental_mrr,
    )
    return commission_input, summary


def calculate_monthly_commission(
    session: Session,
    year: int,
    month: int,
    as_of_date: Optional[date] = None,
) -> MonthlyCommissionAnalytics:
    commission_input, summary = build_monthly_commission_input(session, year, month)
    result = calculate_commission(session, commission_input, as_of_date or last_day_of_month(year, month))
    return MonthlyCommissionAnalytics(sales_summary=summary, commission_result=result)


def add_internet_to_input(commission_input: CommissionInput, additional_quantity: int) -> CommissionInput:
    lines: list[CommissionLineInput] = []
    added = False
    for line in commission_input.lines:
        if line.product_code == BUSINESS_INTERNET_CODE:
            lines.append(
                CommissionLineInput(
                    product_code=line.product_code,
                    quantity=line.quantity + additional_quantity,
                    incremental_mrr=line.incremental_mrr,
                )
            )
            added = True
        else:
            lines.append(line)
    if not added:
        lines.append(CommissionLineInput(BUSINESS_INTERNET_CODE, additional_quantity, ZERO))
    return CommissionInput(
        internet_connects=commission_input.internet_connects + additional_quantity,
        lines=tuple(lines),
    )


def forecast_internet_target(
    session: Session,
    year: int,
    month: int,
    target_internet_connects: int,
) -> CommissionForecast:
    current_input, _ = build_monthly_commission_input(session, year, month)
    current = calculate_monthly_commission(session, year, month)
    if target_internet_connects < current_input.internet_connects:
        raise ValueError("Target Internet connects cannot be lower than current Internet connects.")

    additional_needed = target_internet_connects - current_input.internet_connects
    projected_input = add_internet_to_input(current_input, additional_needed)
    projected_result = calculate_commission(session, projected_input, last_day_of_month(year, month))
    payout_increase = money(projected_result.estimated_payout - current.commission_result.estimated_payout)
    return CommissionForecast(
        current=current,
        target_internet_connects=target_internet_connects,
        additional_internet_needed=additional_needed,
        projected_result=projected_result,
        payout_increase=payout_increase,
    )


def forecast_next_tier(session: Session, year: int, month: int) -> Optional[CommissionForecast]:
    current = calculate_monthly_commission(session, year, month)
    if current.commission_result.next_tier_name is None:
        return None
    internet_needed = current.commission_result.internet_needed_for_next_tier
    if internet_needed is None:
        return None
    target = current.sales_summary.internet_connects + internet_needed
    return forecast_internet_target(session, year, month, target)


def format_currency(value: Optional[Decimal]) -> str:
    if value is None:
        return "n/a"
    return f"${value:,.2f}"


def print_monthly_analytics(analytics: MonthlyCommissionAnalytics, forecast: Optional[CommissionForecast]) -> None:
    summary = analytics.sales_summary
    result = analytics.commission_result
    print("MONTHLY SALES SUMMARY")
    print(f"Eligible sales: {summary.eligible_sale_count}")
    print(f"Excluded sales: {summary.excluded_sale_count}")
    print(f"Internet connects: {summary.internet_connects}")
    print(f"Connected units: {summary.connected_units}")
    print(f"Incremental MRR: {format_currency(summary.total_incremental_mrr)}")
    print("Quantities by product:")
    for total in summary.product_totals:
        print(f"  - {total.product_code}: {total.quantity} ({format_currency(total.incremental_mrr)} MRR)")

    print()
    print("CURRENT COMMISSION")
    print(f"Plan: {result.commission_plan_name}")
    print(f"Tier: {result.tier_name}")
    print(f"Tiered earnings: {format_currency(result.tiered_earnings)}")
    print(f"A-La-Carte earnings: {format_currency(result.a_la_carte_earnings)}")
    print(f"MRR payout: {format_currency(result.mrr_payout)}")
    print(f"Bonus payout: {format_currency(result.bonus_payout)}")
    print(f"Estimated payout: {format_currency(result.estimated_payout)}")

    print()
    print("NEXT-TIER FORECAST")
    if forecast is None:
        print("Next tier: none")
        return
    print(f"Next tier: {analytics.commission_result.next_tier_name}")
    print(f"Additional Internet needed: {forecast.additional_internet_needed}")
    print(f"Projected payout: {format_currency(forecast.projected_result.estimated_payout)}")
    print(f"Payout increase: {format_currency(forecast.payout_increase)}")


if __name__ == "__main__":
    with SessionLocal() as session:
        monthly_analytics = calculate_monthly_commission(session, 2026, 7)
        next_tier_forecast = forecast_next_tier(session, 2026, 7)
        print_monthly_analytics(monthly_analytics, next_tier_forecast)
