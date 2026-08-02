from typing import Optional

import streamlit as st

from app.constants import REFERRAL_PHONE_MAX_CHARS
from app.crud import list_referral_partners
from app.database import SessionLocal
from app.validation import format_us_phone


def referral_partner_options(include_inactive: bool = False):
    with SessionLocal() as session:
        return list_referral_partners(session, include_inactive=include_inactive)


def render_referral_partner_inputs(prefix: str, current_partner_id: Optional[int] = None):
    partners = referral_partner_options(include_inactive=current_partner_id is not None)
    partner_options = [None] + [partner.id for partner in partners]
    partner_lookup = {partner.id: partner for partner in partners}
    index = partner_options.index(current_partner_id) if current_partner_id in partner_options else 0
    selected_partner_id = st.selectbox(
        "Referral partner",
        partner_options,
        index=index,
        format_func=lambda partner_id: "Select partner" if partner_id is None else partner_lookup[partner_id].display_name,
        key=f"{prefix}_partner_select",
    )
    create_new = st.checkbox("Add new referral partner", key=f"{prefix}_new_partner")
    new_partner_values = None
    if create_new:
        cols = st.columns(2)
        first_name = cols[0].text_input("Partner first name", key=f"{prefix}_partner_first")
        last_name = cols[1].text_input("Partner last name", key=f"{prefix}_partner_last")
        organization = cols[0].text_input("Partner organization", key=f"{prefix}_partner_org")
        role_or_type = cols[1].text_input("Partner role/type", key=f"{prefix}_partner_role")
        phone = cols[0].text_input("Partner phone", key=f"{prefix}_partner_phone")
        email = cols[1].text_input("Partner email", key=f"{prefix}_partner_email")
        is_registered = st.checkbox("Registered Spectrum partner", key=f"{prefix}_partner_registered")
        partner_reference = st.text_input("Spectrum partner reference", key=f"{prefix}_partner_reference")
        new_partner_values = {
            "first_name": first_name,
            "last_name": last_name,
            "organization": organization,
            "role_or_type": role_or_type,
            "phone": phone,
            "email": email,
            "is_registered_spectrum_partner": is_registered,
            "spectrum_partner_reference": partner_reference,
        }
    return selected_partner_id, new_partner_values


def render_add_company_referral_section(errors: dict[str, str]) -> None:
    with st.container(border=True):
        st.subheader("Referral partner *")
        st.radio(
            "Referral option",
            ["Select existing referral partner", "Add new referral partner"],
            key="add_company_referral_mode",
        )
        if st.session_state.add_company_referral_mode == "Select existing referral partner":
            partners = referral_partner_options()
            partner_options = [None] + [partner.id for partner in partners]
            partner_lookup = {partner.id: partner for partner in partners}
            st.selectbox(
                "Existing referral partner *",
                partner_options,
                key="add_company_referral_partner_id",
                format_func=lambda partner_id: "Select partner" if partner_id is None else partner_lookup[partner_id].display_name,
            )
        else:
            partner_cols = st.columns(2)
            partner_cols[0].text_input("First name", key="add_company_partner_first")
            partner_cols[1].text_input("Last name", key="add_company_partner_last")
            partner_cols[0].text_input("Organization", key="add_company_partner_org")
            partner_cols[1].text_input("Role / type", key="add_company_partner_role")
            partner_cols[0].text_input("Phone", key="add_company_partner_phone", max_chars=REFERRAL_PHONE_MAX_CHARS)
            if (
                st.session_state.add_company_partner_phone
                and st.session_state.add_company_partner_phone.isdigit()
                and len(st.session_state.add_company_partner_phone) == REFERRAL_PHONE_MAX_CHARS
            ):
                partner_cols[0].caption(format_us_phone(st.session_state.add_company_partner_phone))
            if errors.get("referral_phone"):
                partner_cols[0].error(errors["referral_phone"])
            partner_cols[1].text_input("Email", key="add_company_partner_email")
            if errors.get("referral_email"):
                partner_cols[1].error(errors["referral_email"])
            st.checkbox("Registered Spectrum referral partner", key="add_company_partner_registered")
            st.text_input("Spectrum partner reference", key="add_company_partner_reference")
            st.text_area("Referral partner notes", key="add_company_partner_notes")
        if errors.get("referral"):
            st.error(errors["referral"])
