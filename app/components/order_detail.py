import pandas as pd
import streamlit as st

from app.crud import CrudError, list_company_contacts, list_company_locations
from app.database import SessionLocal
from app.enums import SaleStatus
from app.order_form_state import selected_order_id
from app.order_service import OrderError, get_order, update_order
from app.order_ui_helpers import (
    ORDER_ENTRY_STATUSES,
    order_canceled_message,
    order_display_record,
    order_updated_message,
    order_warning_for_status,
    sale_status_label,
)
from app.opportunity_ui_helpers import contact_label, location_label
from app.ui_helpers import format_currency

from app.components.order_item_editor import render_order_item_editor, render_order_items_read_only


def _render_metric_row(detail) -> None:
    cols = st.columns(4)
    cols[0].metric("Status", detail.summary.status_display)
    cols[1].metric("Items", detail.summary.item_count)
    cols[2].metric("Quantity", detail.summary.total_quantity)
    cols[3].metric("Incremental MRR", format_currency(detail.summary.total_incremental_mrr))


def render_order_detail() -> None:
    order_id = selected_order_id(st.session_state)
    if order_id is None:
        st.info("Select an order from Browse orders.")
        return

    try:
        with SessionLocal() as session:
            detail = get_order(session, order_id)
            locations = list_company_locations(session, detail.summary.company_id, include_inactive=True)
            contacts = list_company_contacts(session, detail.summary.company_id, include_inactive=True)
    except (OrderError, CrudError) as exc:
        st.error(str(exc))
        return

    st.subheader(f"Order - {detail.summary.company_name}")
    _render_metric_row(detail)
    warning = order_warning_for_status(detail.summary.status)
    if warning:
        st.info(warning)

    st.dataframe(pd.DataFrame([order_display_record(detail.summary)]), hide_index=True, width="stretch")

    if detail.summary.status == SaleStatus.INSTALLED:
        with st.expander("Notes", expanded=True):
            notes = st.text_area("Notes", value=detail.notes or "", key=f"order_detail_{order_id}_legacy_notes")
            if st.button("Update notes", type="primary", key=f"order_detail_{order_id}_legacy_update_notes"):
                try:
                    with SessionLocal() as session:
                        update_order(session, order_id, notes=notes)
                    st.success(order_updated_message(order_id))
                    st.rerun()
                except OrderError as exc:
                    st.error(str(exc))
        render_order_items_read_only(detail)
        return

    with st.expander("Edit header", expanded=True):
        location_options = [None, *(location.id for location in locations)]
        contact_options = [None, *(contact.id for contact in contacts)]
        status_options = [status.value for status in ORDER_ENTRY_STATUSES]
        current_status = detail.summary.status.value if detail.summary.status.value in status_options else SaleStatus.DRAFT.value

        cols = st.columns(3)
        order_date = cols[0].date_input("Order date", value=detail.summary.order_date, key=f"order_detail_{order_id}_date")
        location_id = cols[1].selectbox(
            "Location",
            location_options,
            index=location_options.index(detail.summary.location_id) if detail.summary.location_id in location_options else 0,
            key=f"order_detail_{order_id}_location",
            format_func=lambda value: "Unassigned" if value is None else location_label(next(location for location in locations if location.id == value)),
        )
        contact_id = cols[2].selectbox(
            "Contact",
            contact_options,
            index=contact_options.index(detail.summary.contact_id) if detail.summary.contact_id in contact_options else 0,
            key=f"order_detail_{order_id}_contact",
            format_func=lambda value: "Unassigned" if value is None else contact_label(next(contact for contact in contacts if contact.id == value)),
        )

        cols = st.columns(3)
        status = cols[0].selectbox(
            "Status",
            status_options,
            index=status_options.index(current_status),
            key=f"order_detail_{order_id}_status",
            format_func=sale_status_label,
        )
        external_order_number = cols[1].text_input(
            "External order number",
            value=detail.summary.external_order_number or "",
            key=f"order_detail_{order_id}_external",
        )
        customer_account_reference = cols[2].text_input(
            "Customer account reference",
            value=detail.customer_account_reference or "",
            key=f"order_detail_{order_id}_account",
        )
        notes = st.text_area("Notes", value=detail.notes or "", key=f"order_detail_{order_id}_notes")

        if st.button("Update order", type="primary", key=f"order_detail_{order_id}_update"):
            try:
                with SessionLocal() as session:
                    update_order(
                        session,
                        order_id,
                        order_date=order_date,
                        location_id=location_id,
                        contact_id=contact_id,
                        status=status,
                        external_order_number=external_order_number,
                        customer_account_reference=customer_account_reference,
                        notes=notes,
                    )
                st.success(order_updated_message(order_id))
                st.rerun()
            except OrderError as exc:
                st.error(str(exc))

    with st.expander("Cancel order", expanded=False):
        st.caption("Canceled orders remain available for history and do not count toward commission.")
        confirm = st.checkbox("Confirm cancel order", key=f"order_detail_{order_id}_confirm_cancel")
        if st.button("Cancel order", disabled=not confirm, key=f"order_detail_{order_id}_cancel"):
            try:
                with SessionLocal() as session:
                    update_order(session, order_id, status=SaleStatus.CANCELED)
                st.success(order_canceled_message(order_id))
                st.rerun()
            except OrderError as exc:
                st.error(str(exc))

    render_order_item_editor(detail)
