from decimal import Decimal

import pandas as pd
import streamlit as st
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Product
from app.order_service import DuplicateOrderItemError, OrderDetail, OrderError, OrderItemInput, add_order_item, remove_order_item, update_order_item
from app.order_ui_helpers import parse_money_input
from app.ui_helpers import format_currency


def _items_table(detail: OrderDetail) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Product": item.product_name,
                "Quantity": item.quantity,
                "Incremental MRR": format_currency(item.incremental_mrr),
                "Notes": item.notes or "",
            }
            for item in detail.items
        ]
    )


def render_order_items_read_only(detail: OrderDetail) -> None:
    st.markdown("**Items**")
    st.dataframe(_items_table(detail), hide_index=True, width="stretch")


def render_order_item_editor(detail: OrderDetail) -> None:
    st.markdown("**Items**")
    with SessionLocal() as session:
        products = tuple(session.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all())

    for item in detail.items:
        with st.expander(item.product_name, expanded=False):
            cols = st.columns([1, 1, 2])
            quantity = cols[0].number_input(
                "Quantity",
                min_value=1,
                value=int(item.quantity),
                step=1,
                key=f"order_detail_item_{item.id}_quantity",
            )
            incremental_mrr = cols[1].text_input(
                "Incremental MRR",
                value=str(item.incremental_mrr),
                key=f"order_detail_item_{item.id}_mrr",
            )
            notes = cols[2].text_input("Notes", value=item.notes or "", key=f"order_detail_item_{item.id}_notes")
            cols = st.columns([1, 1, 4])
            if cols[0].button("Update item", key=f"order_detail_item_{item.id}_update"):
                amount, error = parse_money_input(incremental_mrr, "Incremental MRR")
                if error:
                    st.error(error)
                else:
                    try:
                        with SessionLocal() as session:
                            update_order_item(session, item.id, quantity=int(quantity), incremental_mrr=amount, notes=notes)
                        st.success("Order item updated.")
                        st.rerun()
                    except OrderError as exc:
                        st.error(str(exc))
            if len(detail.items) > 1:
                confirm = cols[1].checkbox("Confirm remove", key=f"order_detail_item_{item.id}_confirm_remove")
                if cols[2].button("Remove item", key=f"order_detail_item_{item.id}_remove", disabled=not confirm):
                    try:
                        with SessionLocal() as session:
                            remove_order_item(session, item.id)
                        st.success("Order item removed.")
                        st.rerun()
                    except OrderError as exc:
                        st.error(str(exc))

    with st.container(border=True):
        st.markdown("**Add item**")
        product_options = [None, *(product.code for product in products)]
        cols = st.columns([2, 1, 1])
        product_code = cols[0].selectbox(
            "Product",
            product_options,
            key=f"order_detail_{detail.summary.order_id}_add_product",
            format_func=lambda value: "Select product"
            if value is None
            else next(product.name for product in products if product.code == value),
        )
        quantity = cols[1].number_input(
            "Quantity",
            min_value=1,
            value=1,
            step=1,
            key=f"order_detail_{detail.summary.order_id}_add_quantity",
        )
        incremental_mrr = cols[2].text_input("Incremental MRR", value="0.00", key=f"order_detail_{detail.summary.order_id}_add_mrr")
        notes = st.text_input("Item notes", key=f"order_detail_{detail.summary.order_id}_add_notes")
        if st.button("Add item", key=f"order_detail_{detail.summary.order_id}_add_item"):
            if product_code is None:
                st.error("Select a product.")
                return
            amount, error = parse_money_input(incremental_mrr, "Incremental MRR")
            if error:
                st.error(error)
                return
            try:
                with SessionLocal() as session:
                    add_order_item(
                        session,
                        detail.summary.order_id,
                        OrderItemInput(
                            product_code=product_code,
                            quantity=int(quantity),
                            incremental_mrr=amount if amount is not None else Decimal("0.00"),
                            notes=notes,
                        ),
                    )
                st.success("Order item added.")
                st.rerun()
            except DuplicateOrderItemError as exc:
                st.error(str(exc))
            except OrderError as exc:
                st.error(str(exc))
