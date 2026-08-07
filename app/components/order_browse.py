from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import select

from app.crud import CrudError, list_companies
from app.database import SessionLocal
from app.models import Product
from app.order_form_state import ORDER_PAGE_DETAIL, set_order_page_mode, set_selected_order_id
from app.order_service import list_orders
from app.order_ui_helpers import ORDER_BROWSE_STATUSES, order_display_record, sale_status_label
from app.opportunity_service import list_opportunities, opportunity_to_summary


def _load_order_summaries(
    *,
    company_id: Optional[int] = None,
    status: Optional[str] = None,
    product_code: Optional[str] = None,
    opportunity_id: Optional[int] = None,
    order_date_start: Optional[date] = None,
    order_date_end: Optional[date] = None,
    external_order_number: Optional[str] = None,
):
    with SessionLocal() as session:
        return list_orders(
            session,
            company_id=company_id,
            status=status,
            product_code=product_code,
            opportunity_id=opportunity_id,
            order_date_start=order_date_start,
            order_date_end=order_date_end,
            external_order_number=external_order_number,
        )


def render_browse_orders() -> None:
    st.subheader("Browse orders")
    try:
        with SessionLocal() as session:
            companies = list_companies(session, include_archived=False)
            products = tuple(session.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all())
            opportunities = tuple(opportunity_to_summary(row) for row in list_opportunities(session, include_archived=False))
    except CrudError as exc:
        st.error(str(exc))
        return

    company_options = [None, *(company.id for company in companies)]
    product_options = [None, *(product.code for product in products)]
    opportunity_options = [None, *(opportunity.id for opportunity in opportunities)]
    status_options = [None, *(status.value for status in ORDER_BROWSE_STATUSES)]

    with st.container(border=True):
        cols = st.columns(4)
        company_id = cols[0].selectbox(
            "Company",
            company_options,
            key="order_browse_company_id",
            format_func=lambda value: "All companies" if value is None else next(company.name for company in companies if company.id == value),
        )
        status = cols[1].selectbox(
            "Status",
            status_options,
            key="order_browse_status",
            format_func=lambda value: "All statuses" if value is None else sale_status_label(value),
        )
        product_code = cols[2].selectbox(
            "Product",
            product_options,
            key="order_browse_product_code",
            format_func=lambda value: "All products" if value is None else next(product.name for product in products if product.code == value),
        )
        opportunity_id = cols[3].selectbox(
            "Opportunity",
            opportunity_options,
            key="order_browse_opportunity_id",
            format_func=lambda value: "All opportunities"
            if value is None
            else next(opportunity.name for opportunity in opportunities if opportunity.id == value),
        )

        cols = st.columns(3)
        date_range = cols[0].date_input("Order date range", value=None, key="order_browse_date_range")
        external_order_number = cols[1].text_input("External order number", key="order_browse_external_order_number")

    order_date_start = None
    order_date_end = None
    if isinstance(date_range, tuple) and len(date_range) == 2:
        order_date_start, order_date_end = date_range

    try:
        summaries = _load_order_summaries(
            company_id=company_id,
            status=status,
            product_code=product_code,
            opportunity_id=opportunity_id,
            order_date_start=order_date_start,
            order_date_end=order_date_end,
            external_order_number=external_order_number or None,
        )
    except Exception as exc:
        st.error(str(exc))
        return

    st.dataframe(pd.DataFrame([order_display_record(summary) for summary in summaries]), hide_index=True, width="stretch")
    if not summaries:
        st.info("No orders found.")
        return

    selected_id = st.selectbox(
        "Open order detail",
        [summary.order_id for summary in summaries],
        key="order_browse_selected_id",
        format_func=lambda value: next(
            f"{summary.order_date.isoformat()} - {summary.company_name} - {summary.status_display}"
            for summary in summaries
            if summary.order_id == value
        ),
    )
    if st.button("Open order", type="primary"):
        set_selected_order_id(st.session_state, selected_id)
        set_order_page_mode(st.session_state, ORDER_PAGE_DETAIL)
        st.rerun()
