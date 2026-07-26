from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from app.analytics import (
    AnalyticsError,
    CommissionForecast,
    MonthlyCommissionAnalytics,
    calculate_monthly_commission,
    forecast_next_tier,
)
from app.commission import get_active_commission_plan, get_next_tier, get_tier_for_internet_count
from app.database import SessionLocal
from app.models import Product, Sale
from app.seed_demo import DEMO_SALES_MARKER
from app.ui_helpers import MONTH_NAMES, calculate_progress, format_currency, format_percentage, month_label, tier_label


@dataclass(frozen=True)
class DashboardData:
    analytics: MonthlyCommissionAnalytics
    forecast: Optional[CommissionForecast]
    bonus_threshold: int
    current_tier_minimum: int
    next_tier_minimum: Optional[int]
    product_flags: dict[str, tuple[bool, bool]]


def demo_month_exists() -> bool:
    try:
        with SessionLocal() as session:
            count = session.scalar(select(func.count()).select_from(Sale).where(Sale.notes == DEMO_SALES_MARKER))
            return bool(count)
    except Exception:
        return False


@st.cache_data(show_spinner=False)
def load_dashboard_data(year: int, month: int) -> DashboardData:
    with SessionLocal() as session:
        analytics = calculate_monthly_commission(session, year, month)
        forecast = forecast_next_tier(session, year, month)
        plan = get_active_commission_plan(session, analytics.sales_summary.end_date - timedelta(days=1))
        current_tier = get_tier_for_internet_count(plan, analytics.sales_summary.internet_connects)
        next_tier = get_next_tier(plan, analytics.sales_summary.internet_connects)
        product_codes = [total.product_code for total in analytics.sales_summary.product_totals]
        products = session.scalars(select(Product).where(Product.code.in_(product_codes))).all() if product_codes else []
        product_flags = {
            product.code: (product.counts_as_internet_connect, product.counts_as_connected_unit)
            for product in products
        }
        return DashboardData(
            analytics=analytics,
            forecast=forecast,
            bonus_threshold=plan.bonus_unit_threshold,
            current_tier_minimum=current_tier.minimum_internet if current_tier else 0,
            next_tier_minimum=next_tier.minimum_internet if next_tier else None,
            product_flags=product_flags,
        )


def render_kpis(data: DashboardData) -> None:
    summary = data.analytics.sales_summary
    result = data.analytics.commission_result
    columns = st.columns(5)
    columns[0].metric("Estimated Commission", format_currency(result.estimated_payout))
    columns[1].metric("Current Tier", tier_label(result.tier_name))
    columns[2].metric("Internet Connects", summary.internet_connects)
    columns[3].metric("Connected Units", summary.connected_units)
    columns[4].metric("Incremental MRR", format_currency(summary.total_incremental_mrr))


def render_tier_progress(data: DashboardData) -> None:
    result = data.analytics.commission_result
    current = result.internet_connects
    next_target = data.next_tier_minimum
    current_tier_start = data.current_tier_minimum

    st.subheader("Commission Tier Progress")
    if result.next_tier_name is None:
        st.progress(1.0)
        st.success("Highest commission tier reached")
        return

    progress = calculate_progress(current, current_tier_start, next_target)
    cols = st.columns(4)
    cols[0].metric("Current Tier", tier_label(result.tier_name))
    cols[1].metric("Current Internet", current)
    cols[2].metric("Next Tier", tier_label(result.next_tier_name))
    cols[3].metric("Internet Needed", result.internet_needed_for_next_tier)
    st.progress(progress)

    forecast = data.forecast
    projected_payout = forecast.projected_result.estimated_payout if forecast else result.projected_next_tier_payout
    payout_increase = forecast.payout_increase if forecast else result.increase_if_next_tier_reached
    st.info(
        f"{result.internet_needed_for_next_tier} more Internet connects could increase projected commission "
        f"by {format_currency(payout_increase)}."
    )
    cols = st.columns(2)
    cols[0].metric("Projected Payout at Next Tier", format_currency(projected_payout))
    cols[1].metric("Projected Payout Increase", format_currency(payout_increase))


def render_bonus_progress(data: DashboardData) -> None:
    result = data.analytics.commission_result
    connected_units = data.analytics.sales_summary.connected_units
    threshold = data.bonus_threshold
    units_needed = max(threshold - connected_units, 0)
    progress = calculate_progress(connected_units, 0, threshold)

    st.subheader("Monthly Bonus Progress")
    cols = st.columns(5)
    cols[0].metric("Connected Units", connected_units)
    cols[1].metric("Bonus Threshold", threshold)
    cols[2].metric("Units Still Needed", units_needed)
    cols[3].metric("Bonus Unlocked", "Yes" if result.bonus_eligible else "No")
    cols[4].metric("Bonus Payout", format_currency(result.bonus_payout))
    st.progress(progress)
    st.caption(f"Bonus percentage: {format_percentage(result.bonus_percentage)}")
    if result.bonus_eligible:
        st.success("Monthly commission bonus unlocked.")
    else:
        st.info(f"{units_needed} more connected units needed to unlock the monthly bonus.")


def render_commission_breakdown(data: DashboardData) -> None:
    result = data.analytics.commission_result
    st.subheader("Commission Breakdown")
    rows = [
        ("Tiered earnings", result.tiered_earnings),
        ("A-La-Carte earnings", result.a_la_carte_earnings),
        ("MRR payout", result.mrr_payout),
        ("Bonus payout", result.bonus_payout),
        ("Ramp amount", result.ramp_amount),
        ("Estimated payout", result.estimated_payout),
    ]
    table = pd.DataFrame({"Component": [row[0] for row in rows], "Amount": [format_currency(row[1]) for row in rows]})
    st.dataframe(table, hide_index=True, width="stretch")

    chart_rows = rows[:-1]
    chart = pd.DataFrame({"Component": [row[0] for row in chart_rows], "Amount": [float(row[1]) for row in chart_rows]})
    st.bar_chart(chart, x="Component", y="Amount")


def render_product_performance(data: DashboardData) -> None:
    st.subheader("Product Performance")
    totals = data.analytics.sales_summary.product_totals
    if not totals:
        st.info("No product performance data for this month.")
        return

    rows = []
    for total in totals:
        internet_flag, connected_flag = data.product_flags.get(total.product_code, (False, False))
        rows.append(
            {
                "Product": total.product_code,
                "Quantity": total.quantity,
                "Incremental MRR": format_currency(total.incremental_mrr),
                "Counts as Internet Connect": internet_flag,
                "Counts as Connected Unit": connected_flag,
            }
        )
    rows.sort(key=lambda row: (-row["Quantity"], row["Product"]))
    table = pd.DataFrame(rows)
    st.dataframe(table, hide_index=True, width="stretch")
    st.bar_chart(pd.DataFrame(rows), x="Product", y="Quantity")


def render_sales_summary(data: DashboardData) -> None:
    summary = data.analytics.sales_summary
    st.subheader("Monthly Sales Summary")
    total_quantity = sum(total.quantity for total in summary.product_totals)
    cols = st.columns(5)
    cols[0].metric("Eligible Sales", summary.eligible_sale_count)
    cols[1].metric("Excluded Sales", summary.excluded_sale_count)
    cols[2].metric("Date Range", f"{summary.start_date} to {summary.end_date}")
    cols[3].metric("Total Quantity", total_quantity)
    cols[4].metric("Total MRR", format_currency(summary.total_incremental_mrr))
    st.caption(
        "Current MVP logic: Installed sales are commission eligible. Submitted, Scheduled, "
        "Canceled, and Disconnected sales are excluded."
    )


def main() -> None:
    st.set_page_config(page_title="Prospector AI", page_icon=None, layout="wide")
    st.title("Prospector AI")
    st.caption("Sales Performance and Commission Intelligence")

    default_year = 2026 if demo_month_exists() else date.today().year
    default_month = 7 if default_year == 2026 else date.today().month

    with st.sidebar:
        st.header("Dashboard")
        st.radio("Navigation", ["Monthly Performance"], index=0)
        selected_year = st.selectbox("Year", list(range(2025, 2029)), index=list(range(2025, 2029)).index(default_year))
        selected_month = st.selectbox(
            "Month",
            list(range(1, 13)),
            index=default_month - 1,
            format_func=lambda month: MONTH_NAMES[month],
        )
        if st.button("Demo month: July 2026", width="stretch"):
            selected_year = 2026
            selected_month = 7
        if st.button("Refresh", width="stretch"):
            load_dashboard_data.clear()
            st.rerun()

    st.header(month_label(selected_year, selected_month))

    try:
        data = load_dashboard_data(selected_year, selected_month)
    except AnalyticsError as exc:
        st.error(f"Analytics error: {exc}")
        return
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error("Unable to load dashboard data. Confirm the database is initialized and seeded.")
        return

    if data.analytics.sales_summary.eligible_sale_count == 0:
        st.info("No commission-eligible sales found for this month.")

    render_kpis(data)
    st.divider()
    render_tier_progress(data)
    st.divider()
    render_bonus_progress(data)
    st.divider()
    render_commission_breakdown(data)
    st.divider()
    render_product_performance(data)
    st.divider()
    render_sales_summary(data)


if __name__ == "__main__":
    main()
