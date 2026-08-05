from datetime import date
from decimal import Decimal
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import select

from app.constants import OPPORTUNITY_STAGE_LABELS
from app.crud import CrudError, list_companies
from app.database import SessionLocal
from app.models import Product
from app.opportunity_form_state import set_selected_opportunity_id
from app.opportunity_service import list_opportunities, opportunity_to_summary
from app.opportunity_ui_helpers import (
    FOLLOW_UP_ALL,
    FOLLOW_UP_FILTERS,
    filter_summaries,
    opportunity_display_record,
    stage_label,
)


def product_names_for_summary(product_names: tuple[str, ...]) -> str:
    return ", ".join(product_names)


def load_opportunity_summaries(
    *,
    company_id: Optional[int] = None,
    stage: Optional[str] = None,
    product_code: Optional[str] = None,
    include_archived: bool = False,
    expected_close_start: Optional[date] = None,
    expected_close_end: Optional[date] = None,
    minimum_priority_score: Optional[int] = None,
    today: Optional[date] = None,
):
    with SessionLocal() as session:
        opportunities = list_opportunities(
            session,
            company_id=company_id,
            stage=stage,
            include_archived=include_archived,
            product_code=product_code,
            expected_close_start=expected_close_start,
            expected_close_end=expected_close_end,
            minimum_priority_score=minimum_priority_score,
            today=today,
        )
        return tuple(opportunity_to_summary(opportunity, today=today) for opportunity in opportunities)


def render_browse_opportunities() -> None:
    st.subheader("Browse opportunities")
    today = date.today()

    try:
        with SessionLocal() as session:
            companies = list_companies(session, include_archived=False)
            products = tuple(session.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all())
    except CrudError as exc:
        st.error(str(exc))
        return

    company_options = [None, *(company.id for company in companies)]
    product_options = [None, *(product.code for product in products)]
    stage_options = [None, *OPPORTUNITY_STAGE_LABELS.keys()]

    filters = st.container(border=True)
    with filters:
        cols = st.columns(4)
        search = cols[0].text_input("Search by opportunity name", key="opportunity_browse_search")
        company_id = cols[1].selectbox(
            "Company",
            company_options,
            key="opportunity_browse_company_id",
            format_func=lambda value: "All companies"
            if value is None
            else next(company.name for company in companies if company.id == value),
        )
        stage = cols[2].selectbox(
            "Stage",
            stage_options,
            key="opportunity_browse_stage",
            format_func=lambda value: "All stages" if value is None else stage_label(value),
        )
        product_code = cols[3].selectbox(
            "Product",
            product_options,
            key="opportunity_browse_product_code",
            format_func=lambda value: "All products"
            if value is None
            else next(product.name for product in products if product.code == value),
        )

        cols = st.columns(4)
        follow_up_filter = cols[0].selectbox("Follow-up status", list(FOLLOW_UP_FILTERS), index=0, key="opportunity_browse_follow_up")
        include_archived = cols[1].toggle("Show archived", value=False, key="opportunity_browse_include_archived")
        expected_close_range = cols[2].date_input("Expected close date range", value=None, key="opportunity_browse_close_range")
        minimum_priority_score = cols[3].number_input(
            "Minimum priority score",
            min_value=0,
            max_value=100,
            value=0,
            step=1,
            key="opportunity_browse_min_priority",
        )

    expected_close_start = None
    expected_close_end = None
    if isinstance(expected_close_range, tuple) and len(expected_close_range) == 2:
        expected_close_start, expected_close_end = expected_close_range

    try:
        summaries = load_opportunity_summaries(
            company_id=company_id,
            stage=stage,
            product_code=product_code,
            include_archived=include_archived,
            expected_close_start=expected_close_start,
            expected_close_end=expected_close_end,
            minimum_priority_score=int(minimum_priority_score) if minimum_priority_score else None,
            today=today,
        )
    except Exception as exc:
        st.error(str(exc))
        return

    summaries = filter_summaries(
        summaries,
        search=search,
        follow_up_filter=follow_up_filter or FOLLOW_UP_ALL,
        today=today,
    )
    rows = [opportunity_display_record(summary, today) for summary in summaries]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    if not summaries:
        st.info("No opportunities found.")
        return

    selected_id = st.selectbox(
        "Open opportunity detail",
        [summary.id for summary in summaries],
        format_func=lambda value: next(summary.name for summary in summaries if summary.id == value),
        key="opportunity_browse_selected_id",
    )
    if st.button("Open opportunity", type="primary"):
        set_selected_opportunity_id(st.session_state, selected_id)
        st.success("Opportunity detail is available in the Opportunity detail tab.")
