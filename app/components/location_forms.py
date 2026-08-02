import pandas as pd
import streamlit as st

from app.components.display import show_crud_message
from app.constants import LOCATION_TYPE_OPTIONS, STATE_OPTIONS
from app.crud import CrudError, create_location, deactivate_location, list_company_locations, restore_location, update_location
from app.database import SessionLocal
from app.enums import SpectrumRelationship
from app.form_state import set_flash_message
from app.ui_helpers import friendly_label
from app.validation import state_display_label


def render_locations_tab(company_id: int) -> None:
    """Render the company Locations tab."""
    try:
        with SessionLocal() as session:
            include_inactive = st.toggle("Show inactive locations", value=False, key=f"show_inactive_locations_{company_id}")
            locations = list_company_locations(session, company_id, include_inactive=include_inactive)
    except CrudError as exc:
        show_crud_message(exc)
        return
    rows = [
        {
            "Name": location.location_name or "",
            "Address": location.address_line_1,
            "City": location.city,
            "State": location.state,
            "ZIP": location.postal_code,
            "Type": friendly_label(location.location_type),
            "Spectrum status": friendly_label(location.spectrum_relationship),
            "Status": "Active" if location.is_active else f"Inactive: {location.inactive_reason or 'No reason'}",
        }
        for location in locations
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    with st.expander("Add location", expanded=False):
        with st.form(f"add_location_{company_id}"):
            address_line_1 = st.text_input("Street address *")
            address_line_2 = st.text_input("Suite / Unit")
            cols = st.columns(3)
            city = cols[0].text_input("City *")
            state_options = [None] + list(STATE_OPTIONS)
            state = cols[1].selectbox(
                "State *",
                state_options,
                format_func=lambda value: "Select state" if value is None else state_display_label(value),
            )
            postal_code = cols[2].text_input("ZIP code *", max_chars=5)
            location_type_options = [None] + list(LOCATION_TYPE_OPTIONS)
            location_type = st.selectbox(
                "Location type *",
                location_type_options,
                format_func=lambda value: "Select location type" if value is None else value.value,
            )
            location_name = st.text_input("Location label (optional)")
            spectrum_relationship = st.selectbox(
                "Spectrum customer status",
                list(SpectrumRelationship),
                index=list(SpectrumRelationship).index(SpectrumRelationship.UNKNOWN),
                format_func=friendly_label,
            )
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add location", type="primary")
    if submitted:
        try:
            with SessionLocal() as session:
                location = create_location(
                    session,
                    company_id=company_id,
                    location_name=location_name,
                    address_line_1=address_line_1,
                    address_line_2=address_line_2,
                    city=city,
                    state=state,
                    postal_code=postal_code,
                    location_type=location_type,
                    spectrum_relationship=spectrum_relationship,
                    current_provider_notes=notes,
                )
            set_flash_message(st.session_state, f'✅ Location "{location.location_name or "Location"}" added successfully.')
            st.rerun()
        except CrudError as exc:
            show_crud_message(exc)

    if locations:
        st.subheader("Edit location")
        location_ids = [location.id for location in locations]
        selected_location_id = st.selectbox(
            "Select location",
            location_ids,
            format_func=lambda location_id: next(
                (location.location_name or location.address_line_1 for location in locations if location.id == location_id),
                str(location_id),
            ),
        )
        selected = next(location for location in locations if location.id == selected_location_id)
        with st.expander("Selected location edit form", expanded=False):
            with st.form(f"edit_location_{selected.id}"):
                location_name = st.text_input("Location label", value=selected.location_name or "")
                address_line_1 = st.text_input("Address line 1", value=selected.address_line_1)
                address_line_2 = st.text_input("Address line 2", value=selected.address_line_2 or "")
                cols = st.columns(3)
                city = cols[0].text_input("City", value=selected.city)
                state_options = list(STATE_OPTIONS)
                state_index = state_options.index(selected.state) if selected.state in state_options else state_options.index("FL")
                state = cols[1].selectbox(
                    "State *",
                    state_options,
                    index=state_index,
                    format_func=state_display_label,
                )
                postal_code = cols[2].text_input("ZIP code *", value=selected.postal_code, max_chars=5)
                location_type = st.selectbox(
                    "Location type *",
                    list(LOCATION_TYPE_OPTIONS),
                    index=list(LOCATION_TYPE_OPTIONS).index(selected.location_type)
                    if selected.location_type in LOCATION_TYPE_OPTIONS
                    else 0,
                    format_func=lambda value: value.value,
                )
                spectrum_relationship = st.selectbox(
                    "Spectrum customer status",
                    list(SpectrumRelationship),
                    index=list(SpectrumRelationship).index(selected.spectrum_relationship),
                    format_func=friendly_label,
                )
                notes = st.text_area("Notes", value=selected.current_provider_notes or "")
                submitted = st.form_submit_button("Save location", type="primary")
        if submitted:
            try:
                with SessionLocal() as session:
                    location = update_location(
                        session,
                        selected.id,
                        location_name=location_name,
                        address_line_1=address_line_1,
                        address_line_2=address_line_2,
                        city=city,
                        state=state,
                        postal_code=postal_code,
                        location_type=location_type,
                        spectrum_relationship=spectrum_relationship,
                        current_provider_notes=notes,
                    )
                set_flash_message(st.session_state, f'✅ Location "{location.location_name or "Location"}" updated successfully.')
                st.rerun()
            except CrudError as exc:
                show_crud_message(exc)
        with st.expander("Deactivate / restore selected location", expanded=False):
            if selected.is_active:
                reason = st.selectbox(
                    "Inactive reason",
                    ["Closed", "Relocated", "No longer serviced", "Duplicate / entered by mistake", "Other"],
                )
                if st.button("Deactivate location"):
                    try:
                        with SessionLocal() as session:
                            location = deactivate_location(session, selected.id, reason)
                        set_flash_message(st.session_state, f'✅ Location "{location.location_name or "Location"}" marked inactive.')
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)
            else:
                if st.button("Restore location"):
                    try:
                        with SessionLocal() as session:
                            location = restore_location(session, selected.id)
                        set_flash_message(st.session_state, f'✅ Location "{location.location_name or "Location"}" restored successfully.')
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)
