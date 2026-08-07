from datetime import date
from decimal import Decimal

import streamlit as st
from sqlalchemy import select

from app.crud import CrudError, list_companies, list_company_contacts, list_company_locations
from app.database import SessionLocal
from app.enums import SaleStatus
from app.models import Product
from app.order_form_state import (
    add_order_item_row,
    complete_order_creation_success,
    initialize_order_form_state,
    remove_order_item_row,
    sync_order_related_selections,
)
from app.order_service import OrderError, OrderItemInput, create_order_with_items
from app.order_ui_helpers import (
    ORDER_ENTRY_STATUSES,
    order_created_message,
    order_warning_for_status,
    parse_money_input,
    sale_status_label,
    validate_order_item_rows,
)
from app.opportunity_service import list_opportunities, opportunity_to_summary
from app.opportunity_ui_helpers import contact_label, location_label


def render_order_item_rows(
    products: tuple[Product, ...],
    *,
    rows_key: str = "order_item_rows",
    widget_prefix: str = "order_item_row",
    state_prefix: str = "order",
) -> list[dict[str, object]]:
    rows = list(st.session_state.get(rows_key) or [])
    product_options = [None, *(product.code for product in products)]
    updated_rows: list[dict[str, object]] = []
    st.caption("At least one product is required.")

    for index, row in enumerate(rows):
        with st.container(border=True):
            cols = st.columns([2, 1, 1])
            current_code = row.get("product_code")
            product_index = product_options.index(current_code) if current_code in product_options else 0
            product_code = cols[0].selectbox(
                "Product *",
                product_options,
                index=product_index,
                key=f"{widget_prefix}_{index}_product",
                format_func=lambda value: "Select product"
                if value is None
                else next(product.name for product in products if product.code == value),
            )
            quantity = cols[1].number_input(
                "Quantity *",
                min_value=0,
                value=int(row.get("quantity") or 0),
                step=1,
                key=f"{widget_prefix}_{index}_quantity",
            )
            incremental_mrr = cols[2].text_input(
                "Incremental MRR",
                value=str(row.get("incremental_mrr") or "0.00"),
                key=f"{widget_prefix}_{index}_mrr",
            )
            notes = st.text_input("Item notes", value=str(row.get("notes") or ""), key=f"{widget_prefix}_{index}_notes")
            if st.button("Remove item row", key=f"{widget_prefix}_{index}_remove"):
                remove_order_item_row(st.session_state, index, prefix=state_prefix)
                st.rerun()
            updated_rows.append(
                {
                    "product_code": product_code,
                    "quantity": int(quantity),
                    "incremental_mrr": incremental_mrr,
                    "notes": notes,
                    "source_opportunity_product_id": row.get("source_opportunity_product_id"),
                }
            )

    st.session_state[rows_key] = updated_rows
    if st.button("Add item row", key=f"{widget_prefix}_add"):
        add_order_item_row(st.session_state, prefix=state_prefix)
        st.rerun()
    return updated_rows


def _render_errors(errors: dict[str, str], *keys: str) -> None:
    for key in keys:
        if errors.get(key):
            st.error(errors[key])


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


def validate_add_order_ui(rows: list[dict[str, object]]) -> tuple[dict[str, str], list[OrderItemInput]]:
    errors: dict[str, str] = {}
    if st.session_state.get("order_company_id") is None:
        errors["company"] = "Select a company."
    if st.session_state.get("order_date") is None:
        errors["order_date"] = "Order date is required."
    result = validate_order_item_rows(rows)
    errors.update(result.errors)
    item_inputs = _order_items_from_rows(result.valid_rows)
    return errors, item_inputs


def render_add_order_form() -> None:
    st.subheader("Add order")
    initialize_order_form_state(st.session_state)
    errors: dict[str, str] = st.session_state.get("order_errors", {})

    try:
        with SessionLocal() as session:
            companies = list_companies(session, include_archived=False)
            products = tuple(session.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all())
            selected_company_id = st.session_state.get("order_company_id")
            locations = list_company_locations(session, selected_company_id) if selected_company_id else ()
            contacts = list_company_contacts(session, selected_company_id) if selected_company_id else ()
            opportunities = tuple(
                opportunity_to_summary(row)
                for row in list_opportunities(session, company_id=selected_company_id, include_archived=False)
            ) if selected_company_id else ()
    except CrudError as exc:
        st.error(str(exc))
        return

    company_options = [None, *(company.id for company in companies)]
    company_id = st.selectbox(
        "Company *",
        company_options,
        key="order_company_id",
        format_func=lambda value: "Select company" if value is None else next(company.name for company in companies if company.id == value),
    )
    _render_errors(errors, "company")

    location_options = [None, *(location.id for location in locations)]
    contact_options = [None, *(contact.id for contact in contacts)]
    opportunity_options = [None, *(opportunity.id for opportunity in opportunities)]
    sync_order_related_selections(
        st.session_state,
        valid_location_ids={value for value in location_options if value is not None},
        valid_contact_ids={value for value in contact_options if value is not None},
        valid_opportunity_ids={value for value in opportunity_options if value is not None},
    )

    cols = st.columns(3)
    cols[0].selectbox(
        "Location",
        location_options,
        key="order_location_id",
        format_func=lambda value: "Unassigned" if value is None else location_label(next(location for location in locations if location.id == value)),
    )
    cols[1].selectbox(
        "Contact",
        contact_options,
        key="order_contact_id",
        format_func=lambda value: "Unassigned" if value is None else contact_label(next(contact for contact in contacts if contact.id == value)),
    )
    cols[2].selectbox(
        "Source opportunity",
        opportunity_options,
        key="order_opportunity_id",
        format_func=lambda value: "None" if value is None else next(opportunity.name for opportunity in opportunities if opportunity.id == value),
    )

    cols = st.columns(4)
    cols[0].date_input("Order date *", value=st.session_state.get("order_date") or date.today(), key="order_date")
    status = cols[1].selectbox(
        "Status *",
        [status.value for status in ORDER_ENTRY_STATUSES],
        key="order_status",
        format_func=sale_status_label,
    )
    cols[2].text_input("External order number", key="order_external_order_number")
    cols[3].text_input("Customer account reference", key="order_customer_account_reference")
    _render_errors(errors, "order_date")

    warning = order_warning_for_status(status)
    if warning:
        st.info(warning)

    st.text_area("Notes", key="order_notes")
    st.markdown("**Products**")
    rows = render_order_item_rows(products)
    for key, message in errors.items():
        if key.startswith(("products", "product_", "quantity_", "mrr_")):
            st.error(message)

    if st.button("Create order", type="primary"):
        errors, item_inputs = validate_add_order_ui(rows)
        st.session_state.order_errors = errors
        if errors:
            st.rerun()
        try:
            with SessionLocal() as session:
                created = create_order_with_items(
                    session,
                    company_id=int(company_id),
                    location_id=st.session_state.get("order_location_id"),
                    contact_id=st.session_state.get("order_contact_id"),
                    opportunity_id=st.session_state.get("order_opportunity_id"),
                    order_date=st.session_state.get("order_date"),
                    status=SaleStatus(st.session_state.get("order_status")),
                    external_order_number=st.session_state.get("order_external_order_number"),
                    customer_account_reference=st.session_state.get("order_customer_account_reference"),
                    notes=st.session_state.get("order_notes"),
                    items=item_inputs,
                )
            complete_order_creation_success(
                st.session_state,
                order_id=created.order_id,
                flash_message=order_created_message(created.company_name, created.item_count, created.total_incremental_mrr),
                source="add",
            )
            st.rerun()
        except (OrderError, CrudError) as exc:
            st.session_state.order_errors = {"submit": str(exc)}
            st.error(str(exc))
