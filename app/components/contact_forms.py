import pandas as pd
import streamlit as st

from app.components.display import contact_name_label, decision_role_value_label, show_crud_message
from app.constants import CONTACT_TITLE_OPTIONS, CONTACT_TITLE_OTHER
from app.crud import CrudError, create_contact, deactivate_contact, list_company_contacts, list_company_locations, restore_contact, update_contact
from app.database import SessionLocal
from app.enums import ContactRole
from app.form_state import (
    contact_form_key,
    initialize_contact_form_state,
    reset_contact_form_state,
    set_flash_message,
    validate_contact_form_state,
)
from app.ui_helpers import format_phone, friendly_label
from app.validation import title_selection_for_existing


def render_contacts_tab(company_id: int) -> None:
    """Render the company Contacts tab."""
    try:
        with SessionLocal() as session:
            include_inactive = st.toggle("Show inactive contacts", value=False, key=f"show_inactive_contacts_{company_id}")
            contacts = list_company_contacts(session, company_id, include_inactive=include_inactive)
            locations = list_company_locations(session, company_id, include_inactive=True)
    except CrudError as exc:
        show_crud_message(exc)
        return
    location_lookup = {
        location.id: f"{location.location_name or location.address_line_1}{' (inactive)' if not location.is_active else ''}"
        for location in locations
    }
    rows = [
        {
            "Name": contact_name_label(contact.first_name, contact.last_name),
            "Title": contact.job_title or "",
            "Phone": format_phone(contact.phone),
            "Email": contact.email or "",
            "Decision role": friendly_label(contact.decision_role),
            "Primary": contact.is_primary_contact,
            "Assigned location name": location_lookup.get(contact.location_id or 0, "Unassigned"),
            "Status": "Active" if contact.is_active else f"Inactive: {contact.inactive_reason or 'No reason'}",
        }
        for contact in contacts
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    location_options = [None] + [location.id for location in locations]
    location_label = lambda location_id: "Unassigned" if location_id is None else next(
        (
            f"{location.location_name or location.address_line_1}{' (inactive)' if not location.is_active else ''}"
            for location in locations
            if location.id == location_id
        ),
        str(location_id),
    )

    with st.expander("Add contact", expanded=False):
        add_prefix = f"add_contact_{company_id}"
        if st.session_state.get(f"{add_prefix}_reset_pending"):
            reset_contact_form_state(st.session_state, add_prefix)
            st.session_state[f"{add_prefix}_reset_pending"] = False
        initialize_contact_form_state(st.session_state, add_prefix)
        add_errors = st.session_state.get(f"{add_prefix}_errors", {})
        with st.form(f"add_contact_form_{company_id}"):
            st.caption("At least a first name or last name is required.")
            cols = st.columns(2)
            cols[0].text_input("First name", key=contact_form_key(add_prefix, "first_name"))
            cols[1].text_input("Last name", key=contact_form_key(add_prefix, "last_name"))
            if add_errors.get("name"):
                st.error(add_errors["name"])
            title_selection = cols[0].selectbox(
                "Title",
                list(CONTACT_TITLE_OPTIONS),
                key=contact_form_key(add_prefix, "title_selection"),
            )
            if title_selection == CONTACT_TITLE_OTHER:
                cols[0].text_input("Other title", key=contact_form_key(add_prefix, "other_title"))
                if add_errors.get("title"):
                    cols[0].error(add_errors["title"])
            current_location = st.session_state.get(contact_form_key(add_prefix, "location_id"))
            location_index = location_options.index(current_location) if current_location in location_options else 0
            cols[1].selectbox(
                "Assigned location",
                location_options,
                index=location_index,
                format_func=location_label,
                key=contact_form_key(add_prefix, "location_id"),
            )
            cols[0].text_input("Phone", key=contact_form_key(add_prefix, "phone"), max_chars=10)
            phone_value = st.session_state.get(contact_form_key(add_prefix, "phone"))
            if phone_value and str(phone_value).isdigit() and len(str(phone_value)) == 10:
                cols[0].caption(format_phone(str(phone_value)))
            if add_errors.get("phone"):
                cols[0].error(add_errors["phone"])
            cols[1].text_input("Email", key=contact_form_key(add_prefix, "email"))
            if add_errors.get("email"):
                cols[1].error(add_errors["email"])
            role_values = [role.value for role in ContactRole]
            role_current = st.session_state.get(contact_form_key(add_prefix, "decision_role"), ContactRole.UNKNOWN.value)
            role_index = role_values.index(str(role_current)) if str(role_current) in role_values else 0
            st.selectbox(
                "Decision role *",
                role_values,
                index=role_index,
                format_func=decision_role_value_label,
                key=contact_form_key(add_prefix, "decision_role"),
            )
            if add_errors.get("decision_role"):
                st.error(add_errors["decision_role"])
            st.checkbox("Primary contact", key=contact_form_key(add_prefix, "is_primary_contact"))
            st.text_area("Notes", key=contact_form_key(add_prefix, "notes"))
            submitted = st.form_submit_button("Add contact", type="primary")
    if submitted:
        payload, errors = validate_contact_form_state(st.session_state, add_prefix)
        st.session_state[f"{add_prefix}_errors"] = errors
        if errors:
            st.rerun()
        try:
            with SessionLocal() as session:
                create_contact(
                    session,
                    company_id=company_id,
                    location_id=payload["location_id"],
                    first_name=payload["first_name"],
                    last_name=payload["last_name"],
                    job_title=payload["job_title"],
                    phone=payload["phone"],
                    email=payload["email"],
                    decision_role=payload["decision_role"],
                    is_primary_contact=bool(payload["is_primary_contact"]),
                    notes=payload["notes"],
                )
            name = contact_name_label(payload.get("first_name"), payload.get("last_name"))
            st.session_state[f"{add_prefix}_errors"] = {}
            st.session_state[f"{add_prefix}_reset_pending"] = True
            set_flash_message(st.session_state, f'✅ Contact "{name}" added successfully.')
            st.rerun()
        except CrudError as exc:
            show_crud_message(exc)

    if contacts:
        st.subheader("Edit contact")
        contact_ids = [contact.id for contact in contacts]
        selected_contact_id = st.selectbox(
            "Select contact",
            contact_ids,
            format_func=lambda contact_id: next(
                (
                    f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email or contact.phone or str(contact_id)
                    for contact in contacts
                    if contact.id == contact_id
                ),
                str(contact_id),
            ),
        )
        selected = next(contact for contact in contacts if contact.id == selected_contact_id)
        with st.expander("Selected contact edit form", expanded=False):
            edit_prefix = f"edit_contact_{selected.id}"
            initialize_contact_form_state(
                st.session_state,
                edit_prefix,
                {
                    "first_name": selected.first_name or "",
                    "last_name": selected.last_name or "",
                    "title_selection": title_selection_for_existing(selected.job_title)[0],
                    "other_title": title_selection_for_existing(selected.job_title)[1],
                    "location_id": selected.location_id,
                    "phone": selected.phone or "",
                    "email": selected.email or "",
                    "decision_role": selected.decision_role.value,
                    "is_primary_contact": selected.is_primary_contact,
                    "notes": selected.notes or "",
                },
            )
            edit_errors = st.session_state.get(f"{edit_prefix}_errors", {})
            with st.form(f"edit_contact_form_{selected.id}"):
                st.caption("At least a first name or last name is required.")
                cols = st.columns(2)
                cols[0].text_input("First name", key=contact_form_key(edit_prefix, "first_name"))
                cols[1].text_input("Last name", key=contact_form_key(edit_prefix, "last_name"))
                if edit_errors.get("name"):
                    st.error(edit_errors["name"])
                edit_title_selection = cols[0].selectbox(
                    "Title",
                    list(CONTACT_TITLE_OPTIONS),
                    key=contact_form_key(edit_prefix, "title_selection"),
                )
                if edit_title_selection == CONTACT_TITLE_OTHER:
                    cols[0].text_input("Other title", key=contact_form_key(edit_prefix, "other_title"))
                    if edit_errors.get("title"):
                        cols[0].error(edit_errors["title"])
                current_location = st.session_state.get(contact_form_key(edit_prefix, "location_id"))
                location_index = location_options.index(current_location) if current_location in location_options else 0
                cols[1].selectbox(
                    "Assigned location",
                    location_options,
                    index=location_index,
                    format_func=location_label,
                    key=contact_form_key(edit_prefix, "location_id"),
                )
                cols[0].text_input("Phone", key=contact_form_key(edit_prefix, "phone"), max_chars=10)
                edit_phone_value = st.session_state.get(contact_form_key(edit_prefix, "phone"))
                if edit_phone_value and str(edit_phone_value).isdigit() and len(str(edit_phone_value)) == 10:
                    cols[0].caption(format_phone(str(edit_phone_value)))
                if edit_errors.get("phone"):
                    cols[0].error(edit_errors["phone"])
                cols[1].text_input("Email", key=contact_form_key(edit_prefix, "email"))
                if edit_errors.get("email"):
                    cols[1].error(edit_errors["email"])
                role_values = [role.value for role in ContactRole]
                edit_role_current = st.session_state.get(contact_form_key(edit_prefix, "decision_role"), ContactRole.UNKNOWN)
                edit_role_value = edit_role_current.value if isinstance(edit_role_current, ContactRole) else str(edit_role_current)
                edit_role_index = role_values.index(edit_role_value) if edit_role_value in role_values else 0
                st.selectbox(
                    "Decision role *",
                    role_values,
                    index=edit_role_index,
                    format_func=decision_role_value_label,
                    key=contact_form_key(edit_prefix, "decision_role"),
                )
                if edit_errors.get("decision_role"):
                    st.error(edit_errors["decision_role"])
                st.checkbox("Primary contact", key=contact_form_key(edit_prefix, "is_primary_contact"))
                st.text_area("Notes", key=contact_form_key(edit_prefix, "notes"))
                submitted = st.form_submit_button("Save contact", type="primary")
        if submitted:
            payload, errors = validate_contact_form_state(st.session_state, edit_prefix)
            st.session_state[f"{edit_prefix}_errors"] = errors
            if errors:
                st.rerun()
            try:
                with SessionLocal() as session:
                    update_contact(
                        session,
                        selected.id,
                        location_id=payload["location_id"],
                        first_name=payload["first_name"],
                        last_name=payload["last_name"],
                        job_title=payload["job_title"],
                        phone=payload["phone"],
                        email=payload["email"],
                        decision_role=payload["decision_role"],
                        is_primary_contact=bool(payload["is_primary_contact"]),
                        notes=payload["notes"],
                    )
                name = contact_name_label(payload.get("first_name"), payload.get("last_name"))
                st.session_state[f"{edit_prefix}_errors"] = {}
                set_flash_message(st.session_state, f'✅ Contact "{name}" updated successfully.')
                st.rerun()
            except CrudError as exc:
                show_crud_message(exc)
        with st.expander("Deactivate / restore selected contact", expanded=False):
            if selected.is_active:
                reason = st.text_input("Inactive reason", value="No longer with company")
                if st.button("Mark no longer with company"):
                    try:
                        with SessionLocal() as session:
                            deactivate_contact(session, selected.id, reason)
                        set_flash_message(
                            st.session_state,
                            f'✅ Contact "{contact_name_label(selected.first_name, selected.last_name)}" marked as no longer with the company.',
                        )
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)
            else:
                if st.button("Restore contact"):
                    try:
                        with SessionLocal() as session:
                            restore_contact(session, selected.id)
                        set_flash_message(
                            st.session_state,
                            f'✅ Contact "{contact_name_label(selected.first_name, selected.last_name)}" restored successfully.',
                        )
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)
