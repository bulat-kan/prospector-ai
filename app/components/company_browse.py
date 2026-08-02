import pandas as pd
import streamlit as st

from app.components.display import lead_source_label, show_crud_message
from app.crud import CrudError, list_companies
from app.database import SessionLocal
from app.ui_helpers import format_phone, normalize_website_url


def render_browse_companies() -> None:
    """Render company search, active/archive filter, table, and selection."""
    st.subheader("Browse companies")
    search = st.text_input("Search by company name", key="company_search")
    include_archived = st.toggle("Show archived companies", value=False)
    try:
        with SessionLocal() as session:
            companies = list_companies(session, search=search, include_archived=include_archived)
    except CrudError as exc:
        show_crud_message(exc)
        return

    rows = [
        {
            "Company": company.name,
            "Industry": company.industry or "",
            "Phone": format_phone(company.main_phone),
            "Website": normalize_website_url(company.website),
            "Lead source": lead_source_label(company.lead_source),
            "Referral partner": company.referral_partner_name or "",
            "Locations": company.location_count,
            "Contacts": company.contact_count,
            "Open opportunities": company.opportunity_count,
            "Status": "Active" if company.is_active else "Archived",
        }
        for company in companies
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if not companies:
        st.info("No companies found.")
        return

    company_ids = [company.id for company in companies]
    current_id = st.session_state.get("selected_company_id")
    index = company_ids.index(current_id) if current_id in company_ids else 0
    selected_id = st.selectbox(
        "Open company detail",
        company_ids,
        index=index,
        format_func=lambda company_id: next(company.name for company in companies if company.id == company_id),
    )
    st.session_state.selected_company_id = selected_id
    st.info("The selected company is available in the Company detail tab below.")
