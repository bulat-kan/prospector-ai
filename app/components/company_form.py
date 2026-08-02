import streamlit as st

from app.components.display import lead_source_label, lead_source_options
from app.components.referral_forms import render_add_company_referral_section
from app.constants import INDUSTRY_OPTIONS, INDUSTRY_OTHER, LEAD_SOURCE_REFERRAL
from app.crud import CrudError, DuplicateRecordError, ValidationError, create_company_with_referral_partner
from app.database import SessionLocal
from app.form_state import initialize_add_company_form_state, reset_add_company_form_state, validate_add_company_form_state
from app.validation import format_us_phone


def render_add_company_form() -> None:
    """Render the Add Company workflow and inline referral partner section."""
    st.subheader("Add company")
    if st.session_state.get("add_company_reset_pending"):
        reset_add_company_form_state(st.session_state)
        st.session_state.add_company_reset_pending = False
    initialize_add_company_form_state(st.session_state)
    if st.session_state.get("add_company_success"):
        st.success(st.session_state.add_company_success)
        st.session_state.add_company_success = ""

    errors = st.session_state.get("add_company_errors", {})
    if errors.get("submit"):
        st.error(errors["submit"])
    st.caption("* Required fields")
    st.text_input("Company name *", placeholder="Acme Services LLC", key="add_company_name")
    if errors.get("name"):
        st.error(errors["name"])

    cols = st.columns(2)
    cols[0].text_input("Public phone", key="add_company_phone", max_chars=10)
    if st.session_state.add_company_phone and st.session_state.add_company_phone.isdigit() and len(st.session_state.add_company_phone) == 10:
        cols[0].caption(format_us_phone(st.session_state.add_company_phone))
    cols[1].text_input("Website", key="add_company_website", placeholder="example.com")
    if errors.get("phone"):
        cols[0].error(errors["phone"])
    if errors.get("website"):
        cols[1].error(errors["website"])

    industry = cols[0].selectbox(
        "Industry *",
        list(INDUSTRY_OPTIONS),
        key="add_company_industry",
    )
    if industry == INDUSTRY_OTHER:
        cols[0].text_input("Other industry *", key="add_company_other_industry")
    lead_source = cols[1].selectbox(
        "Lead source *",
        lead_source_options(),
        key="add_company_lead_source",
        format_func=lead_source_label,
    )
    if errors.get("industry"):
        cols[0].error(errors["industry"])
    if errors.get("lead_source"):
        cols[1].error(errors["lead_source"])

    if lead_source == LEAD_SOURCE_REFERRAL:
        render_add_company_referral_section(errors)

    st.text_area("Notes", key="add_company_notes")
    submitted = st.button("Create company", type="primary")
    if submitted:
        st.session_state.add_company_referral_phone_error = ""
        st.session_state.add_company_referral_email_error = ""
        company_payload, partner_payload, errors = validate_add_company_form_state(st.session_state)
        st.session_state.add_company_referral_phone_error = errors.get("referral_phone", "")
        st.session_state.add_company_referral_email_error = errors.get("referral_email", "")
        st.session_state.add_company_errors = errors
        if errors:
            st.rerun()
        try:
            with SessionLocal() as session:
                company = create_company_with_referral_partner(
                    session,
                    company_fields=company_payload,
                    referral_partner_fields=partner_payload,
                )
            st.session_state.selected_company_id = company.id
            st.session_state.add_company_success = f"Created {company.name}."
            st.session_state.add_company_errors = {}
            st.session_state.add_company_referral_phone_error = ""
            st.session_state.add_company_referral_email_error = ""
            st.session_state.add_company_reset_pending = True
            st.rerun()
        except (CrudError, DuplicateRecordError, ValidationError) as exc:
            st.session_state.add_company_errors = {"submit": str(exc)}
            st.error(str(exc))
