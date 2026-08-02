import streamlit as st

from app.components.company_browse import render_browse_companies
from app.components.company_form import render_add_company_form
from app.components.company_overview import render_company_overview
from app.components.contact_forms import render_contacts_tab
from app.components.display import show_crud_message
from app.components.flash_messages import render_flash_message
from app.components.location_forms import render_locations_tab
from app.crud import CrudError, RecordNotFoundError, get_company
from app.database import SessionLocal


def render_company_detail() -> None:
    """Render the selected company detail tabs."""
    company_id = st.session_state.get("selected_company_id")
    if company_id is None:
        st.info("Select a company to open its detail view.")
        return
    try:
        with SessionLocal() as session:
            company = get_company(session, company_id)
    except RecordNotFoundError:
        st.session_state.selected_company_id = None
        st.info("The selected company no longer exists.")
        return
    except CrudError as exc:
        show_crud_message(exc)
        return

    st.header(company.name)
    overview, locations, contacts = st.tabs(["Overview", "Locations", "Contacts"])
    with overview:
        render_company_overview(company.id)
    with locations:
        render_locations_tab(company.id)
    with contacts:
        render_contacts_tab(company.id)


def render_companies_page() -> None:
    """Render company browsing, creation, and detail management."""
    st.header("Companies")
    render_flash_message()
    browse_tab, add_tab, detail_tab = st.tabs(["Browse companies", "Add company", "Company detail"])
    with browse_tab:
        render_browse_companies()
    with add_tab:
        render_add_company_form()
    with detail_tab:
        render_company_detail()
