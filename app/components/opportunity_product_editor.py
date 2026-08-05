from decimal import Decimal

import streamlit as st
from sqlalchemy import select

from app.database import SessionLocal
from app.form_state import set_flash_message
from app.models import Product
from app.opportunity_service import (
    DuplicateOpportunityProductError,
    OpportunityProductDTO,
    OpportunityProductInput,
    add_opportunity_product,
    remove_opportunity_product,
    update_opportunity_product,
)
from app.opportunity_ui_helpers import INTEREST_LEVELS, parse_money_input
from app.ui_helpers import format_currency


def _active_products() -> tuple[Product, ...]:
    with SessionLocal() as session:
        return tuple(session.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all())


def render_add_product_to_opportunity(opportunity_id: int, existing_codes: set[str]) -> None:
    products = _active_products()
    with st.expander("Add product"):
        product_codes = [product.code for product in products]
        product_code = st.selectbox(
            "Product",
            [None, *product_codes],
            key=f"detail_add_product_{opportunity_id}",
            format_func=lambda value: "Select product"
            if value is None
            else next(product.name for product in products if product.code == value),
        )
        cols = st.columns(3)
        quantity = cols[0].number_input("Estimated quantity", min_value=0, value=1, step=1, key=f"detail_add_quantity_{opportunity_id}")
        mrr = cols[1].text_input("Estimated incremental MRR", value="0.00", key=f"detail_add_mrr_{opportunity_id}")
        interest = cols[2].selectbox("Interest level", list(INTEREST_LEVELS), key=f"detail_add_interest_{opportunity_id}")
        notes = st.text_input("Notes", key=f"detail_add_notes_{opportunity_id}")
        if st.button("Add product", type="primary", key=f"detail_add_submit_{opportunity_id}"):
            if product_code is None:
                st.error("Select a product.")
                return
            if product_code in existing_codes:
                st.error("This product is already included in the opportunity.")
                return
            amount, error = parse_money_input(mrr, "Estimated incremental MRR")
            if error:
                st.error(error)
                return
            try:
                with SessionLocal() as session:
                    add_opportunity_product(
                        session,
                        opportunity_id,
                        OpportunityProductInput(
                            product_code=product_code,
                            estimated_quantity=int(quantity),
                            estimated_incremental_mrr=amount or Decimal("0.00"),
                            interest_level=interest,
                            notes=notes,
                        ),
                    )
                set_flash_message(st.session_state, "✅ Product added to opportunity.")
                st.rerun()
            except DuplicateOpportunityProductError as exc:
                st.error(str(exc))


def render_existing_product_editor(row: OpportunityProductDTO) -> None:
    with st.container(border=True):
        st.markdown(f"**{row.product_name}**")
        cols = st.columns(4)
        quantity = cols[0].number_input(
            "Estimated quantity",
            min_value=0,
            value=row.estimated_quantity,
            step=1,
            key=f"detail_product_{row.id}_quantity",
        )
        mrr = cols[1].text_input(
            "Estimated incremental MRR",
            value=f"{row.estimated_incremental_mrr:.2f}",
            key=f"detail_product_{row.id}_mrr",
        )
        interest = cols[2].selectbox(
            "Interest level",
            list(INTEREST_LEVELS),
            index=list(INTEREST_LEVELS).index(row.interest_level or "Unknown"),
            key=f"detail_product_{row.id}_interest",
        )
        cols[3].metric("Current MRR", format_currency(row.estimated_incremental_mrr))
        notes = st.text_input("Notes", value=row.notes or "", key=f"detail_product_{row.id}_notes")

        with st.container(horizontal=True):
            if st.button("Update product", key=f"detail_product_{row.id}_update"):
                amount, error = parse_money_input(mrr, "Estimated incremental MRR")
                if error:
                    st.error(error)
                    return
                with SessionLocal() as session:
                    update_opportunity_product(
                        session,
                        row.id,
                        estimated_quantity=int(quantity),
                        estimated_incremental_mrr=amount,
                        interest_level=interest,
                        notes=notes,
                    )
                set_flash_message(st.session_state, "✅ Opportunity product updated.")
                st.rerun()
            confirm_key = f"confirm_remove_opportunity_product_{row.id}"
            if not st.session_state.get(confirm_key):
                if st.button("Remove product", key=f"detail_product_{row.id}_remove"):
                    st.session_state[confirm_key] = True
                    st.rerun()
            else:
                st.warning("Confirm removing this product row.")
                if st.button("Confirm remove", key=f"detail_product_{row.id}_confirm_remove"):
                    with SessionLocal() as session:
                        remove_opportunity_product(session, row.id)
                    st.session_state[confirm_key] = False
                    set_flash_message(st.session_state, "✅ Opportunity product removed.")
                    st.rerun()
                if st.button("Cancel", key=f"detail_product_{row.id}_cancel_remove"):
                    st.session_state[confirm_key] = False
                    st.rerun()


def render_opportunity_product_editor(opportunity_id: int, products: tuple[OpportunityProductDTO, ...]) -> None:
    st.subheader("Products")
    existing_codes = {product.product_code for product in products}
    if not products:
        st.info("No products are attached to this opportunity.")
    for product in products:
        render_existing_product_editor(product)
    render_add_product_to_opportunity(opportunity_id, existing_codes)
