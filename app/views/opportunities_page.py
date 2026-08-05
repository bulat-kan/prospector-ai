import streamlit as st

from app.components.flash_messages import render_flash_message
from app.components.opportunity_browse import render_browse_opportunities
from app.components.opportunity_detail import render_opportunity_detail
from app.components.opportunity_form import render_add_opportunity_form


def render_opportunities_page() -> None:
    """Render opportunity browsing, creation, detail, and product management."""
    st.header("Opportunities")
    render_flash_message()
    browse_tab, add_tab, detail_tab = st.tabs(["Browse opportunities", "Add opportunity", "Opportunity detail"])
    with browse_tab:
        render_browse_opportunities()
    with add_tab:
        render_add_opportunity_form()
    with detail_tab:
        render_opportunity_detail()
