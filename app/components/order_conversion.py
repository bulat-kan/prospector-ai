from datetime import date
from decimal import Decimal

import streamlit as st
from sqlalchemy import select

from app.crud import CrudError, list_company_contacts, list_company_locations
from app.database import SessionLocal
from app.enums import SaleStatus
from app.models import Product
from app.order_form_state import complete_order_creation_success, initialize_order_form_state, sync_order_related_selections
from app.order_service import (
    OrderError,
    OrderItemInput,
    build_order_preview_from_opportunity,
    create_order_from_opportunity,
)
from app.order_ui_helpers import (
    ORDER_ENTRY_STATUSES,
    order_created_from_opportunity_message,
    order_warning_for_status,
    sale_status_label,
    validate_order_item_rows,
)
from app.opportunity_service import list_opportunities, opportunity_to_summary
from app.opportunity_ui_helpers import contact_label, location_label

from app.components.order_form import render_order_item_rows


def _populate_preview_state(preview) -> None:
    st.session_state.convert_loaded_opportunity_id = preview.opportunity_id
    st.session_state.convert_location_id = preview.location_id
    st.session_state.convert_contact_id = preview.primary_contact_id
    st.session_state.convert_order_date = preview.suggested_order_date
    st.session_state.convert_item_rows = [
        {
            "product_code": item.product_code,
            "quantity": item.quantity,
            "incremental_mrr": str(item.incremental_mrr),
            "notes": item.notes or "",
            "source_opportunity_product_id": item.opportunity_product_id,
        }
        for item in preview.suggested_items
    ] or [{"product_code": None, "quantity": 1, "incremental_mrr": "0.00", "notes": "", "source_opportunity_product_id": None}]


def _order_items_from_rows(rows: tuple[dict[str, object], ...]) -> list[OrderItemInput]:
    return [
        OrderItemInput(
            product_code=str(row["product_code"]),
            quantity=int(row.get("quantity") or 0),
            incremental_mrr=row.get("incremental_mrr") if isinstance(row.get("incremental_mrr"), Decimal) else Decimal("0.00"),
            notes=str(row.get("notes") or ""),
            source_opportunity_product_id=row.get("source_opportunity_product_id"),  # type: ignore[arg-type]
        )
        for row in rows
    ]


def render_convert_opportunity_to_order() -> None:
    st.subheader("Convert opportunity")
    initialize_order_form_state(st.session_state)
    errors: dict[str, str] = st.session_state.get("convert_errors", {})

    try:
        with SessionLocal() as session:
            opportunities = tuple(opportunity_to_summary(row) for row in list_opportunities(session, include_archived=False))
            products = tuple(session.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all())
    except CrudError as exc:
        st.error(str(exc))
        return

    opportunity_options = [None, *(opportunity.id for opportunity in opportunities)]
    opportunity_id = st.selectbox(
        "Opportunity *",
        opportunity_options,
        key="convert_opportunity_id",
        format_func=lambda value: "Select opportunity"
        if value is None
        else next(f"{opportunity.name} - {opportunity.company_name}" for opportunity in opportunities if opportunity.id == value),
    )
    if errors.get("opportunity"):
        st.error(errors["opportunity"])
    if opportunity_id is None:
        st.info("Select an opportunity to preview an order.")
        return

    try:
        with SessionLocal() as session:
            preview = build_order_preview_from_opportunity(session, int(opportunity_id))
            locations = list_company_locations(session, preview.company_id)
            contacts = list_company_contacts(session, preview.company_id)
    except (OrderError, CrudError) as exc:
        st.error(str(exc))
        return

    if st.session_state.get("convert_loaded_opportunity_id") != preview.opportunity_id:
        _populate_preview_state(preview)

    st.write(f"Company: {preview.company_name}")
    st.write(f"Suggested items: {len(preview.suggested_items)}")

    location_options = [None, *(location.id for location in locations)]
    contact_options = [None, *(contact.id for contact in contacts)]
    sync_order_related_selections(
        st.session_state,
        valid_location_ids={value for value in location_options if value is not None},
        valid_contact_ids={value for value in contact_options if value is not None},
        valid_opportunity_ids=set(),
        prefix="convert",
    )

    cols = st.columns(2)
    cols[0].selectbox(
        "Location",
        location_options,
        key="convert_location_id",
        format_func=lambda value: "Unassigned" if value is None else location_label(next(location for location in locations if location.id == value)),
    )
    cols[1].selectbox(
        "Contact",
        contact_options,
        key="convert_contact_id",
        format_func=lambda value: "Unassigned" if value is None else contact_label(next(contact for contact in contacts if contact.id == value)),
    )

    cols = st.columns(4)
    cols[0].date_input("Order date *", value=st.session_state.get("convert_order_date") or date.today(), key="convert_order_date")
    status = cols[1].selectbox(
        "Status *",
        [status.value for status in ORDER_ENTRY_STATUSES],
        key="convert_status",
        format_func=sale_status_label,
    )
    cols[2].text_input("External order number", key="convert_external_order_number")
    cols[3].text_input("Customer account reference", key="convert_customer_account_reference")

    warning = order_warning_for_status(status)
    if warning:
        st.info(warning)

    st.text_area("Notes", key="convert_notes")
    st.markdown("**Products**")
    rows = render_order_item_rows(
        products,
        rows_key="convert_item_rows",
        widget_prefix="convert_order_item_row",
        state_prefix="convert",
    )
    for key, message in errors.items():
        if key.startswith(("products", "product_", "quantity_", "mrr_")):
            st.error(message)

    if st.button("Create order from opportunity", type="primary"):
        form_errors: dict[str, str] = {}
        if opportunity_id is None:
            form_errors["opportunity"] = "Select an opportunity."
        if st.session_state.get("convert_order_date") is None:
            form_errors["order_date"] = "Order date is required."
        validation = validate_order_item_rows(rows)
        form_errors.update(validation.errors)
        st.session_state.convert_errors = form_errors
        if form_errors:
            st.rerun()
        try:
            with SessionLocal() as session:
                created = create_order_from_opportunity(
                    session,
                    opportunity_id=int(opportunity_id),
                    location_id=st.session_state.get("convert_location_id"),
                    contact_id=st.session_state.get("convert_contact_id"),
                    order_date=st.session_state.get("convert_order_date"),
                    status=SaleStatus(st.session_state.get("convert_status")),
                    external_order_number=st.session_state.get("convert_external_order_number"),
                    customer_account_reference=st.session_state.get("convert_customer_account_reference"),
                    notes=st.session_state.get("convert_notes"),
                    item_inputs=_order_items_from_rows(validation.valid_rows),
                )
            complete_order_creation_success(
                st.session_state,
                order_id=created.order_id,
                flash_message=order_created_from_opportunity_message(created.opportunity_name, created.company_name),
                source="convert",
            )
            st.rerun()
        except (OrderError, CrudError) as exc:
            st.session_state.convert_errors = {"submit": str(exc)}
            st.error(str(exc))
