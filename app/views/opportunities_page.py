import streamlit as st

from app.components.flash_messages import render_flash_message
from app.components.opportunity_browse import render_browse_opportunities
from app.components.opportunity_detail import render_opportunity_detail
from app.components.opportunity_form import render_add_opportunity_form
from app.opportunity_form_state import (
    OPPORTUNITY_PAGE_ADD,
    OPPORTUNITY_PAGE_BROWSE,
    OPPORTUNITY_PAGE_DETAIL,
    OPPORTUNITY_PAGE_MODES,
    apply_pending_opportunity_form_reset,
    initialize_opportunity_form_state,
)


def render_opportunities_page() -> None:
    """Render opportunity browsing, creation, detail, and product management."""
    initialize_opportunity_form_state(st.session_state)
    apply_pending_opportunity_form_reset(st.session_state)
    st.header("Opportunities")
    render_flash_message()
    mode = st.segmented_control(
        "Opportunity section",
        OPPORTUNITY_PAGE_MODES,
        key="opportunity_page_mode",
    )
    if mode == OPPORTUNITY_PAGE_BROWSE:
        render_browse_opportunities()
    elif mode == OPPORTUNITY_PAGE_ADD:
        render_add_opportunity_form()
    elif mode == OPPORTUNITY_PAGE_DETAIL:
        render_opportunity_detail()
