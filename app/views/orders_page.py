import streamlit as st

from app.components.flash_messages import render_flash_message
from app.components.order_browse import render_browse_orders
from app.components.order_conversion import render_convert_opportunity_to_order
from app.components.order_detail import render_order_detail
from app.components.order_form import render_add_order_form
from app.order_form_state import (
    ORDER_PAGE_ADD,
    ORDER_PAGE_BROWSE,
    ORDER_PAGE_CONVERT,
    ORDER_PAGE_DETAIL,
    ORDER_PAGE_MODES,
    apply_pending_order_form_reset,
    initialize_order_form_state,
)


def render_orders_page() -> None:
    initialize_order_form_state(st.session_state)
    apply_pending_order_form_reset(st.session_state)

    st.header("Orders")
    render_flash_message()
    mode = st.segmented_control("Order section", ORDER_PAGE_MODES, key="order_page_mode")

    if mode == ORDER_PAGE_BROWSE:
        render_browse_orders()
    elif mode == ORDER_PAGE_ADD:
        render_add_order_form()
    elif mode == ORDER_PAGE_CONVERT:
        render_convert_opportunity_to_order()
    elif mode == ORDER_PAGE_DETAIL:
        render_order_detail()
