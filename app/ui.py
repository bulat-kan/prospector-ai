import streamlit as st

from app.views.companies_page import render_companies_page
from app.views.dashboard_page import render_dashboard_page
from app.views.opportunities_page import render_opportunities_page


PAGE_DASHBOARD = "Dashboard"
PAGE_COMPANIES = "Companies"
PAGE_OPPORTUNITIES = "Opportunities"
NAVIGATION_PAGES = (PAGE_DASHBOARD, PAGE_COMPANIES, PAGE_OPPORTUNITIES)


def configure_page() -> None:
    st.set_page_config(page_title="Prospector AI", page_icon=None, layout="wide")
    st.title("Prospector AI")
    st.caption("Sales Performance and Commission Intelligence")


def render_navigation() -> str:
    with st.sidebar:
        st.header("Navigation")
        return st.radio("Page", list(NAVIGATION_PAGES), index=0)


def main() -> None:
    """Configure the Streamlit shell and route to the selected page."""
    configure_page()
    page = render_navigation()

    if page == PAGE_DASHBOARD:
        render_dashboard_page()
    elif page == PAGE_COMPANIES:
        render_companies_page()
    elif page == PAGE_OPPORTUNITIES:
        render_opportunities_page()


if __name__ == "__main__":
    main()
