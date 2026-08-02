import streamlit as st

from app.components.display import lead_source_label, lead_source_options, show_crud_message
from app.components.referral_forms import render_referral_partner_inputs
from app.constants import LEAD_SOURCE_REFERRAL
from app.crud import (
    CrudError,
    archive_company,
    create_referral_partner,
    get_company,
    restore_company,
    update_company,
)
from app.database import SessionLocal
from app.form_state import set_flash_message
from app.ui_helpers import format_phone, normalize_website_url


def render_company_overview(company_id: int) -> None:
    """Render company summary, edit form, and archive/restore controls."""
    try:
        with SessionLocal() as session:
            company = get_company(session, company_id)
    except CrudError as exc:
        show_crud_message(exc)
        return

    cols = st.columns(4)
    cols[0].metric("Locations", company.location_count)
    cols[1].metric("Contacts", company.contact_count)
    cols[2].metric("Open opportunities", company.opportunity_count)
    cols[3].metric("Lead source", lead_source_label(company.lead_source))
    with st.container(border=True):
        st.write(f"**Industry:** {company.industry or 'Not set'}")
        st.write(f"**Phone:** {format_phone(company.main_phone) or 'Not set'}")
        website = normalize_website_url(company.website)
        st.write(f"**Website:** {website or 'Not set'}")
        st.write(f"**Status:** {'Active' if company.is_active else 'Archived'}")
        st.write(f"**Referral partner:** {company.referral_partner_name or 'None'}")
        if company.lead_source_legacy:
            st.write(f"**Legacy lead source:** {company.lead_source_legacy}")
        st.write(f"**Notes:** {company.notes or 'None'}")

    with st.expander("Edit company", expanded=False):
        with st.form(f"edit_company_{company.id}"):
            name = st.text_input("Company name", value=company.name)
            cols = st.columns(2)
            main_phone = cols[0].text_input("Public phone", value=company.main_phone or "")
            website = cols[1].text_input("Website", value=company.website or "")
            industry = cols[0].text_input("Industry", value=company.industry or "")
            options = lead_source_options()
            lead_index = options.index(company.lead_source) if company.lead_source in options else 0
            lead_source = cols[1].selectbox("Lead source", options, index=lead_index, format_func=lead_source_label)
            referral_partner_id = company.referral_partner_id
            new_partner_values = None
            if lead_source == LEAD_SOURCE_REFERRAL:
                referral_partner_id, new_partner_values = render_referral_partner_inputs(
                    f"edit_company_{company.id}",
                    current_partner_id=company.referral_partner_id,
                )
                if referral_partner_id is None:
                    referral_partner_id = company.referral_partner_id
            notes = st.text_area("Notes", value=company.notes or "")
            submitted = st.form_submit_button("Save company", type="primary")
    if submitted:
        try:
            with SessionLocal() as session:
                if lead_source == LEAD_SOURCE_REFERRAL and new_partner_values is not None:
                    partner = create_referral_partner(session, **new_partner_values)
                    referral_partner_id = partner.id
                update_company(
                    session,
                    company.id,
                    name=name,
                    main_phone=main_phone,
                    website=website,
                    industry=industry,
                    lead_source=lead_source,
                    referral_partner_id=referral_partner_id if lead_source == LEAD_SOURCE_REFERRAL else None,
                    notes=notes,
                )
            st.success("Company updated.")
            st.rerun()
        except CrudError as exc:
            show_crud_message(exc)

    with st.expander("Archive / restore company", expanded=False):
        if company.is_active:
            confirmed = st.checkbox("Confirm archive", key=f"archive_company_confirm_{company.id}")
            if st.button("Archive company", disabled=not confirmed):
                try:
                    with SessionLocal() as session:
                        archive_company(session, company.id)
                    set_flash_message(st.session_state, "Company archived.")
                    st.rerun()
                except CrudError as exc:
                    show_crud_message(exc)
        else:
            if st.button("Restore company"):
                try:
                    with SessionLocal() as session:
                        restore_company(session, company.id)
                    set_flash_message(st.session_state, "Company restored.")
                    st.rerun()
                except CrudError as exc:
                    show_crud_message(exc)
