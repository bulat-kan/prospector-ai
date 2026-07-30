from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from app.analytics import (
    AnalyticsError,
    CommissionForecast,
    MonthlyCommissionAnalytics,
    calculate_monthly_commission,
    forecast_next_tier,
)
from app.commission import get_active_commission_plan, get_next_tier, get_tier_for_internet_count
from app.crud import (
    CrudError,
    DuplicateRecordError,
    RecordNotFoundError,
    ValidationError,
    archive_company,
    create_company,
    create_contact,
    create_location,
    create_referral_partner,
    deactivate_contact,
    deactivate_location,
    get_company,
    list_companies,
    list_company_contacts,
    list_company_locations,
    list_referral_partners,
    restore_company,
    restore_contact,
    restore_location,
    update_company,
    update_contact,
    update_location,
)
from app.database import SessionLocal
from app.enums import ContactRole, LocationType, SpectrumRelationship, TerritoryStatus
from app.models import Product, Sale
from app.seed_demo import DEMO_SALES_MARKER
from app.ui_helpers import (
    MONTH_NAMES,
    calculate_progress,
    format_currency,
    format_percentage,
    format_phone,
    friendly_label,
    month_label,
    normalize_website_url,
    tier_label,
)
from app.validation import LEAD_SOURCE_AE_FOUND, LEAD_SOURCE_LABELS, LEAD_SOURCE_REFERRAL


@dataclass(frozen=True)
class DashboardData:
    analytics: MonthlyCommissionAnalytics
    forecast: Optional[CommissionForecast]
    bonus_threshold: int
    current_tier_minimum: int
    next_tier_minimum: Optional[int]
    product_flags: dict[str, tuple[bool, bool]]


def demo_month_exists() -> bool:
    try:
        with SessionLocal() as session:
            count = session.scalar(select(func.count()).select_from(Sale).where(Sale.notes == DEMO_SALES_MARKER))
            return bool(count)
    except Exception:
        return False


@st.cache_data(show_spinner=False)
def load_dashboard_data(year: int, month: int) -> DashboardData:
    with SessionLocal() as session:
        analytics = calculate_monthly_commission(session, year, month)
        forecast = forecast_next_tier(session, year, month)
        plan = get_active_commission_plan(session, analytics.sales_summary.end_date - timedelta(days=1))
        current_tier = get_tier_for_internet_count(plan, analytics.sales_summary.internet_connects)
        next_tier = get_next_tier(plan, analytics.sales_summary.internet_connects)
        product_codes = [total.product_code for total in analytics.sales_summary.product_totals]
        products = session.scalars(select(Product).where(Product.code.in_(product_codes))).all() if product_codes else []
        product_flags = {
            product.code: (product.counts_as_internet_connect, product.counts_as_connected_unit)
            for product in products
        }
        return DashboardData(
            analytics=analytics,
            forecast=forecast,
            bonus_threshold=plan.bonus_unit_threshold,
            current_tier_minimum=current_tier.minimum_internet if current_tier else 0,
            next_tier_minimum=next_tier.minimum_internet if next_tier else None,
            product_flags=product_flags,
        )


def render_kpis(data: DashboardData) -> None:
    summary = data.analytics.sales_summary
    result = data.analytics.commission_result
    columns = st.columns(5)
    columns[0].metric("Estimated Commission", format_currency(result.estimated_payout))
    columns[1].metric("Current Tier", tier_label(result.tier_name))
    columns[2].metric("Internet Connects", summary.internet_connects)
    columns[3].metric("Connected Units", summary.connected_units)
    columns[4].metric("Incremental MRR", format_currency(summary.total_incremental_mrr))


def render_tier_progress(data: DashboardData) -> None:
    result = data.analytics.commission_result
    current = result.internet_connects
    next_target = data.next_tier_minimum
    current_tier_start = data.current_tier_minimum

    st.subheader("Commission Tier Progress")
    if result.next_tier_name is None:
        st.progress(1.0)
        st.success("Highest commission tier reached")
        return

    progress = calculate_progress(current, current_tier_start, next_target)
    cols = st.columns(4)
    cols[0].metric("Current Tier", tier_label(result.tier_name))
    cols[1].metric("Current Internet", current)
    cols[2].metric("Next Tier", tier_label(result.next_tier_name))
    cols[3].metric("Internet Needed", result.internet_needed_for_next_tier)
    st.progress(progress)

    forecast = data.forecast
    projected_payout = forecast.projected_result.estimated_payout if forecast else result.projected_next_tier_payout
    payout_increase = forecast.payout_increase if forecast else result.increase_if_next_tier_reached
    st.info(
        f"{result.internet_needed_for_next_tier} more Internet connects could increase projected commission "
        f"by {format_currency(payout_increase)}."
    )
    cols = st.columns(2)
    cols[0].metric("Projected Payout at Next Tier", format_currency(projected_payout))
    cols[1].metric("Projected Payout Increase", format_currency(payout_increase))


def render_bonus_progress(data: DashboardData) -> None:
    result = data.analytics.commission_result
    connected_units = data.analytics.sales_summary.connected_units
    threshold = data.bonus_threshold
    units_needed = max(threshold - connected_units, 0)
    progress = calculate_progress(connected_units, 0, threshold)

    st.subheader("Monthly Bonus Progress")
    cols = st.columns(5)
    cols[0].metric("Connected Units", connected_units)
    cols[1].metric("Bonus Threshold", threshold)
    cols[2].metric("Units Still Needed", units_needed)
    cols[3].metric("Bonus Unlocked", "Yes" if result.bonus_eligible else "No")
    cols[4].metric("Bonus Payout", format_currency(result.bonus_payout))
    st.progress(progress)
    st.caption(f"Bonus percentage: {format_percentage(result.bonus_percentage)}")
    if result.bonus_eligible:
        st.success("Monthly commission bonus unlocked.")
    else:
        st.info(f"{units_needed} more connected units needed to unlock the monthly bonus.")


def render_commission_breakdown(data: DashboardData) -> None:
    result = data.analytics.commission_result
    st.subheader("Commission Breakdown")
    rows = [
        ("Tiered earnings", result.tiered_earnings),
        ("A-La-Carte earnings", result.a_la_carte_earnings),
        ("MRR payout", result.mrr_payout),
        ("Bonus payout", result.bonus_payout),
        ("Ramp amount", result.ramp_amount),
        ("Estimated payout", result.estimated_payout),
    ]
    table = pd.DataFrame({"Component": [row[0] for row in rows], "Amount": [format_currency(row[1]) for row in rows]})
    st.dataframe(table, hide_index=True, width="stretch")

    chart_rows = rows[:-1]
    chart = pd.DataFrame({"Component": [row[0] for row in chart_rows], "Amount": [float(row[1]) for row in chart_rows]})
    st.bar_chart(chart, x="Component", y="Amount")


def render_product_performance(data: DashboardData) -> None:
    st.subheader("Product Performance")
    totals = data.analytics.sales_summary.product_totals
    if not totals:
        st.info("No product performance data for this month.")
        return

    rows = []
    for total in totals:
        internet_flag, connected_flag = data.product_flags.get(total.product_code, (False, False))
        rows.append(
            {
                "Product": total.product_code,
                "Quantity": total.quantity,
                "Incremental MRR": format_currency(total.incremental_mrr),
                "Counts as Internet Connect": internet_flag,
                "Counts as Connected Unit": connected_flag,
            }
        )
    rows.sort(key=lambda row: (-row["Quantity"], row["Product"]))
    table = pd.DataFrame(rows)
    st.dataframe(table, hide_index=True, width="stretch")
    st.bar_chart(pd.DataFrame(rows), x="Product", y="Quantity")


def render_sales_summary(data: DashboardData) -> None:
    summary = data.analytics.sales_summary
    st.subheader("Monthly Sales Summary")
    total_quantity = sum(total.quantity for total in summary.product_totals)
    cols = st.columns(5)
    cols[0].metric("Eligible Sales", summary.eligible_sale_count)
    cols[1].metric("Excluded Sales", summary.excluded_sale_count)
    cols[2].metric("Date Range", f"{summary.start_date} to {summary.end_date}")
    cols[3].metric("Total Quantity", total_quantity)
    cols[4].metric("Total MRR", format_currency(summary.total_incremental_mrr))
    st.caption(
        "Current MVP logic: Installed sales are commission eligible. Submitted, Scheduled, "
        "Canceled, and Disconnected sales are excluded."
    )


def render_dashboard_page() -> None:
    default_year = 2026 if demo_month_exists() else date.today().year
    default_month = 7 if default_year == 2026 else date.today().month

    with st.sidebar:
        st.subheader("Dashboard filters")
        selected_year = st.selectbox("Year", list(range(2025, 2029)), index=list(range(2025, 2029)).index(default_year))
        selected_month = st.selectbox(
            "Month",
            list(range(1, 13)),
            index=default_month - 1,
            format_func=lambda month: MONTH_NAMES[month],
        )
        if st.button("Demo month: July 2026", width="stretch"):
            selected_year = 2026
            selected_month = 7
        if st.button("Refresh dashboard", width="stretch"):
            load_dashboard_data.clear()
            st.rerun()

    st.header(month_label(selected_year, selected_month))

    try:
        data = load_dashboard_data(selected_year, selected_month)
    except AnalyticsError as exc:
        st.error(f"Analytics error: {exc}")
        return
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error("Unable to load dashboard data. Confirm the database is initialized and seeded.")
        return

    if data.analytics.sales_summary.eligible_sale_count == 0:
        st.info("No commission-eligible sales found for this month.")

    render_kpis(data)
    st.divider()
    render_tier_progress(data)
    st.divider()
    render_bonus_progress(data)
    st.divider()
    render_commission_breakdown(data)
    st.divider()
    render_product_performance(data)
    st.divider()
    render_sales_summary(data)


def show_crud_message(error: Exception) -> None:
    st.error(str(error))


def company_options(search: str = ""):
    with SessionLocal() as session:
        return list_companies(session, search=search)


def lead_source_options() -> list[Optional[str]]:
    return [None, LEAD_SOURCE_AE_FOUND, LEAD_SOURCE_REFERRAL]


def lead_source_label(value: Optional[str]) -> str:
    if value is None:
        return "Not set"
    return LEAD_SOURCE_LABELS.get(value, friendly_label(value))


def referral_partner_options(include_inactive: bool = False):
    with SessionLocal() as session:
        return list_referral_partners(session, include_inactive=include_inactive)


def render_referral_partner_inputs(prefix: str, current_partner_id: Optional[int] = None):
    partners = referral_partner_options(include_inactive=current_partner_id is not None)
    partner_options = [None] + [partner.id for partner in partners]
    partner_lookup = {partner.id: partner for partner in partners}
    index = partner_options.index(current_partner_id) if current_partner_id in partner_options else 0
    selected_partner_id = st.selectbox(
        "Referral partner",
        partner_options,
        index=index,
        format_func=lambda partner_id: "Select partner" if partner_id is None else partner_lookup[partner_id].display_name,
        key=f"{prefix}_partner_select",
    )
    create_new = st.checkbox("Add new referral partner", key=f"{prefix}_new_partner")
    new_partner_values = None
    if create_new:
        cols = st.columns(2)
        first_name = cols[0].text_input("Partner first name", key=f"{prefix}_partner_first")
        last_name = cols[1].text_input("Partner last name", key=f"{prefix}_partner_last")
        organization = cols[0].text_input("Partner organization", key=f"{prefix}_partner_org")
        role_or_type = cols[1].text_input("Partner role/type", key=f"{prefix}_partner_role")
        phone = cols[0].text_input("Partner phone", key=f"{prefix}_partner_phone")
        email = cols[1].text_input("Partner email", key=f"{prefix}_partner_email")
        is_registered = st.checkbox("Registered Spectrum partner", key=f"{prefix}_partner_registered")
        partner_reference = st.text_input("Spectrum partner reference", key=f"{prefix}_partner_reference")
        new_partner_values = {
            "first_name": first_name,
            "last_name": last_name,
            "organization": organization,
            "role_or_type": role_or_type,
            "phone": phone,
            "email": email,
            "is_registered_spectrum_partner": is_registered,
            "spectrum_partner_reference": partner_reference,
        }
    return selected_partner_id, new_partner_values


def render_add_company_form() -> None:
    st.subheader("Add company")
    with st.form("add_company_form", clear_on_submit=True):
        name = st.text_input("Company name", placeholder="Acme Services LLC")
        cols = st.columns(2)
        main_phone = cols[0].text_input("Public phone")
        website = cols[1].text_input("Website")
        industry = cols[0].text_input("Industry")
        lead_source = cols[1].selectbox("Lead source", lead_source_options(), format_func=lead_source_label)
        referral_partner_id = None
        new_partner_values = None
        if lead_source == LEAD_SOURCE_REFERRAL:
            referral_partner_id, new_partner_values = render_referral_partner_inputs("add_company")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Create company", type="primary")
    if submitted:
        try:
            with SessionLocal() as session:
                if lead_source == LEAD_SOURCE_REFERRAL and new_partner_values is not None:
                    partner = create_referral_partner(session, **new_partner_values)
                    referral_partner_id = partner.id
                company = create_company(
                    session,
                    name=name,
                    main_phone=main_phone,
                    website=website,
                    industry=industry,
                    lead_source=lead_source,
                    referral_partner_id=referral_partner_id,
                    notes=notes,
                )
            st.session_state.selected_company_id = company.id
            st.success(f"Created {company.name}.")
            st.rerun()
        except (CrudError, DuplicateRecordError, ValidationError) as exc:
            show_crud_message(exc)


def render_browse_companies() -> None:
    st.subheader("Browse companies")
    search = st.text_input("Search by company name", key="company_search")
    include_archived = st.toggle("Show archived companies", value=False)
    try:
        with SessionLocal() as session:
            companies = list_companies(session, search=search, include_archived=include_archived)
    except CrudError as exc:
        show_crud_message(exc)
        return

    rows = [
        {
            "Company": company.name,
            "Industry": company.industry or "",
            "Phone": format_phone(company.main_phone),
            "Website": normalize_website_url(company.website),
            "Lead source": lead_source_label(company.lead_source),
            "Referral partner": company.referral_partner_name or "",
            "Locations": company.location_count,
            "Contacts": company.contact_count,
            "Open opportunities": company.opportunity_count,
            "Status": "Active" if company.is_active else "Archived",
        }
        for company in companies
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if not companies:
        st.info("No companies found.")
        return

    company_ids = [company.id for company in companies]
    current_id = st.session_state.get("selected_company_id")
    index = company_ids.index(current_id) if current_id in company_ids else 0
    selected_id = st.selectbox(
        "Open company detail",
        company_ids,
        index=index,
        format_func=lambda company_id: next(company.name for company in companies if company.id == company_id),
    )
    st.session_state.selected_company_id = selected_id
    st.info("The selected company is available in the Company detail tab below.")


def render_company_overview(company_id: int) -> None:
    try:
        with SessionLocal() as session:
            company = get_company(session, company_id)
    except CrudError as exc:
        show_crud_message(exc)
        return

    cols = st.columns(4)
    cols[0].metric("Locations", company.location_count)
    cols[1].metric("Contacts", company.contact_count)
    cols[2].metric("Open opportunities", company.opportunity_count)
    cols[3].metric("Lead source", lead_source_label(company.lead_source))
    with st.container(border=True):
        st.write(f"**Industry:** {company.industry or 'Not set'}")
        st.write(f"**Phone:** {format_phone(company.main_phone) or 'Not set'}")
        website = normalize_website_url(company.website)
        st.write(f"**Website:** {website or 'Not set'}")
        st.write(f"**Status:** {'Active' if company.is_active else 'Archived'}")
        st.write(f"**Referral partner:** {company.referral_partner_name or 'None'}")
        if company.lead_source_legacy:
            st.write(f"**Legacy lead source:** {company.lead_source_legacy}")
        st.write(f"**Notes:** {company.notes or 'None'}")

    with st.expander("Edit company", expanded=False):
        with st.form(f"edit_company_{company.id}"):
            name = st.text_input("Company name", value=company.name)
            cols = st.columns(2)
            main_phone = cols[0].text_input("Public phone", value=company.main_phone or "")
            website = cols[1].text_input("Website", value=company.website or "")
            industry = cols[0].text_input("Industry", value=company.industry or "")
            options = lead_source_options()
            lead_index = options.index(company.lead_source) if company.lead_source in options else 0
            lead_source = cols[1].selectbox("Lead source", options, index=lead_index, format_func=lead_source_label)
            referral_partner_id = company.referral_partner_id
            new_partner_values = None
            if lead_source == LEAD_SOURCE_REFERRAL:
                referral_partner_id, new_partner_values = render_referral_partner_inputs(
                    f"edit_company_{company.id}",
                    current_partner_id=company.referral_partner_id,
                )
                if referral_partner_id is None:
                    referral_partner_id = company.referral_partner_id
            notes = st.text_area("Notes", value=company.notes or "")
            submitted = st.form_submit_button("Save company", type="primary")
    if submitted:
        try:
            with SessionLocal() as session:
                if lead_source == LEAD_SOURCE_REFERRAL and new_partner_values is not None:
                    partner = create_referral_partner(session, **new_partner_values)
                    referral_partner_id = partner.id
                update_company(
                    session,
                    company.id,
                    name=name,
                    main_phone=main_phone,
                    website=website,
                    industry=industry,
                    lead_source=lead_source,
                    referral_partner_id=referral_partner_id if lead_source == LEAD_SOURCE_REFERRAL else None,
                    notes=notes,
                )
            st.success("Company updated.")
            st.rerun()
        except CrudError as exc:
            show_crud_message(exc)

    with st.expander("Archive / restore company", expanded=False):
        if company.is_active:
            confirmed = st.checkbox("Confirm archive", key=f"archive_company_confirm_{company.id}")
            if st.button("Archive company", disabled=not confirmed):
                try:
                    with SessionLocal() as session:
                        archive_company(session, company.id)
                    st.success("Company archived.")
                    st.rerun()
                except CrudError as exc:
                    show_crud_message(exc)
        else:
            if st.button("Restore company"):
                try:
                    with SessionLocal() as session:
                        restore_company(session, company.id)
                    st.success("Company restored.")
                    st.rerun()
                except CrudError as exc:
                    show_crud_message(exc)


def render_locations_tab(company_id: int) -> None:
    try:
        with SessionLocal() as session:
            include_inactive = st.toggle("Show inactive locations", value=False, key=f"show_inactive_locations_{company_id}")
            locations = list_company_locations(session, company_id, include_inactive=include_inactive)
    except CrudError as exc:
        show_crud_message(exc)
        return
    rows = [
        {
            "Name": location.location_name or "",
            "Address": location.address_line_1,
            "City": location.city,
            "State": location.state,
            "ZIP": location.postal_code,
            "Type": friendly_label(location.location_type),
            "Spectrum status": friendly_label(location.spectrum_relationship),
            "Status": "Active" if location.is_active else f"Inactive: {location.inactive_reason or 'No reason'}",
        }
        for location in locations
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    with st.expander("Add location", expanded=False):
        with st.form(f"add_location_{company_id}", clear_on_submit=True):
            location_name = st.text_input("Location label")
            address_line_1 = st.text_input("Address line 1")
            address_line_2 = st.text_input("Address line 2")
            cols = st.columns(3)
            city = cols[0].text_input("City")
            state = cols[1].text_input("State")
            postal_code = cols[2].text_input("ZIP code")
            location_type = st.selectbox("Location type", list(LocationType), format_func=friendly_label)
            spectrum_relationship = st.selectbox(
                "Spectrum customer status",
                list(SpectrumRelationship),
                index=list(SpectrumRelationship).index(SpectrumRelationship.UNKNOWN),
                format_func=friendly_label,
            )
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add location", type="primary")
    if submitted:
        try:
            with SessionLocal() as session:
                create_location(
                    session,
                    company_id=company_id,
                    location_name=location_name,
                    address_line_1=address_line_1,
                    address_line_2=address_line_2,
                    city=city,
                    state=state,
                    postal_code=postal_code,
                    location_type=location_type,
                    spectrum_relationship=spectrum_relationship,
                    current_provider_notes=notes,
                )
            st.success("Location added.")
            st.rerun()
        except CrudError as exc:
            show_crud_message(exc)

    if locations:
        st.subheader("Edit location")
        location_ids = [location.id for location in locations]
        selected_location_id = st.selectbox(
            "Select location",
            location_ids,
            format_func=lambda location_id: next(
                (location.location_name or location.address_line_1 for location in locations if location.id == location_id),
                str(location_id),
            ),
        )
        selected = next(location for location in locations if location.id == selected_location_id)
        with st.expander("Selected location edit form", expanded=False):
            with st.form(f"edit_location_{selected.id}"):
                location_name = st.text_input("Location label", value=selected.location_name or "")
                address_line_1 = st.text_input("Address line 1", value=selected.address_line_1)
                address_line_2 = st.text_input("Address line 2", value=selected.address_line_2 or "")
                cols = st.columns(3)
                city = cols[0].text_input("City", value=selected.city)
                state = cols[1].text_input("State", value=selected.state)
                postal_code = cols[2].text_input("ZIP code", value=selected.postal_code)
                location_type = st.selectbox(
                    "Location type",
                    list(LocationType),
                    index=list(LocationType).index(selected.location_type),
                    format_func=friendly_label,
                )
                spectrum_relationship = st.selectbox(
                    "Spectrum customer status",
                    list(SpectrumRelationship),
                    index=list(SpectrumRelationship).index(selected.spectrum_relationship),
                    format_func=friendly_label,
                )
                notes = st.text_area("Notes", value=selected.current_provider_notes or "")
                submitted = st.form_submit_button("Save location", type="primary")
        if submitted:
            try:
                with SessionLocal() as session:
                    update_location(
                        session,
                        selected.id,
                        location_name=location_name,
                        address_line_1=address_line_1,
                        address_line_2=address_line_2,
                        city=city,
                        state=state,
                        postal_code=postal_code,
                        location_type=location_type,
                        spectrum_relationship=spectrum_relationship,
                        current_provider_notes=notes,
                    )
                st.success("Location updated.")
                st.rerun()
            except CrudError as exc:
                show_crud_message(exc)
        with st.expander("Deactivate / restore selected location", expanded=False):
            if selected.is_active:
                reason = st.selectbox(
                    "Inactive reason",
                    ["Closed", "Relocated", "No longer serviced", "Duplicate / entered by mistake", "Other"],
                )
                if st.button("Deactivate location"):
                    try:
                        with SessionLocal() as session:
                            deactivate_location(session, selected.id, reason)
                        st.success("Location marked inactive.")
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)
            else:
                if st.button("Restore location"):
                    try:
                        with SessionLocal() as session:
                            restore_location(session, selected.id)
                        st.success("Location restored.")
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)


def render_contacts_tab(company_id: int) -> None:
    try:
        with SessionLocal() as session:
            include_inactive = st.toggle("Show inactive contacts", value=False, key=f"show_inactive_contacts_{company_id}")
            contacts = list_company_contacts(session, company_id, include_inactive=include_inactive)
            locations = list_company_locations(session, company_id)
    except CrudError as exc:
        show_crud_message(exc)
        return
    location_lookup = {location.id: location.location_name or location.address_line_1 for location in locations}
    rows = [
        {
            "Name": f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email or contact.phone or "",
            "Title": contact.job_title or "",
            "Phone": format_phone(contact.phone),
            "Email": contact.email or "",
            "Decision role": friendly_label(contact.decision_role),
            "Primary": contact.is_primary_contact,
            "Assigned location name": location_lookup.get(contact.location_id or 0, "Unassigned"),
            "Status": "Active" if contact.is_active else f"Inactive: {contact.inactive_reason or 'No reason'}",
        }
        for contact in contacts
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    location_options = [None] + [location.id for location in locations]
    location_label = lambda location_id: "Unassigned" if location_id is None else next(
        (location.location_name or location.address_line_1 for location in locations if location.id == location_id),
        str(location_id),
    )

    with st.expander("Add contact", expanded=False):
        with st.form(f"add_contact_{company_id}", clear_on_submit=True):
            cols = st.columns(2)
            first_name = cols[0].text_input("First name")
            last_name = cols[1].text_input("Last name")
            job_title = cols[0].text_input("Title")
            location_id = cols[1].selectbox("Assigned location", location_options, format_func=location_label)
            phone = cols[0].text_input("Phone")
            email = cols[1].text_input("Email")
            is_decision_maker = st.checkbox("Decision-maker contact")
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add contact", type="primary")
    if submitted:
        try:
            with SessionLocal() as session:
                create_contact(
                    session,
                    company_id=company_id,
                    location_id=location_id,
                    first_name=first_name,
                    last_name=last_name,
                    job_title=job_title,
                    phone=phone,
                    email=email,
                    decision_role=ContactRole.DECISION_MAKER if is_decision_maker else ContactRole.UNKNOWN,
                    is_primary_contact=is_decision_maker,
                    notes=notes,
                )
            st.success("Contact added.")
            st.rerun()
        except CrudError as exc:
            show_crud_message(exc)

    if contacts:
        st.subheader("Edit contact")
        contact_ids = [contact.id for contact in contacts]
        selected_contact_id = st.selectbox(
            "Select contact",
            contact_ids,
            format_func=lambda contact_id: next(
                (
                    f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.email or contact.phone or str(contact_id)
                    for contact in contacts
                    if contact.id == contact_id
                ),
                str(contact_id),
            ),
        )
        selected = next(contact for contact in contacts if contact.id == selected_contact_id)
        with st.expander("Selected contact edit form", expanded=False):
            with st.form(f"edit_contact_{selected.id}"):
                cols = st.columns(2)
                first_name = cols[0].text_input("First name", value=selected.first_name or "")
                last_name = cols[1].text_input("Last name", value=selected.last_name or "")
                job_title = cols[0].text_input("Title", value=selected.job_title or "")
                location_index = location_options.index(selected.location_id) if selected.location_id in location_options else 0
                location_id = cols[1].selectbox("Assigned location", location_options, index=location_index, format_func=location_label)
                phone = cols[0].text_input("Phone", value=selected.phone or "")
                email = cols[1].text_input("Email", value=selected.email or "")
                is_decision_maker = st.checkbox(
                    "Decision-maker contact",
                    value=selected.decision_role == ContactRole.DECISION_MAKER or selected.is_primary_contact,
                )
                notes = st.text_area("Notes", value=selected.notes or "")
                submitted = st.form_submit_button("Save contact", type="primary")
        if submitted:
            try:
                with SessionLocal() as session:
                    update_contact(
                        session,
                        selected.id,
                        location_id=location_id,
                        first_name=first_name,
                        last_name=last_name,
                        job_title=job_title,
                        phone=phone,
                        email=email,
                        decision_role=ContactRole.DECISION_MAKER if is_decision_maker else ContactRole.UNKNOWN,
                        is_primary_contact=is_decision_maker,
                        notes=notes,
                    )
                st.success("Contact updated.")
                st.rerun()
            except CrudError as exc:
                show_crud_message(exc)
        with st.expander("Deactivate / restore selected contact", expanded=False):
            if selected.is_active:
                reason = st.text_input("Inactive reason", value="No longer with company")
                if st.button("Mark no longer with company"):
                    try:
                        with SessionLocal() as session:
                            deactivate_contact(session, selected.id, reason)
                        st.success("Contact marked inactive.")
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)
            else:
                if st.button("Restore contact"):
                    try:
                        with SessionLocal() as session:
                            restore_contact(session, selected.id)
                        st.success("Contact restored.")
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)


def render_company_detail() -> None:
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
    st.header("Companies")
    browse_tab, add_tab, detail_tab = st.tabs(["Browse companies", "Add company", "Company detail"])
    with browse_tab:
        render_browse_companies()
    with add_tab:
        render_add_company_form()
    with detail_tab:
        render_company_detail()


def main() -> None:
    st.set_page_config(page_title="Prospector AI", page_icon=None, layout="wide")
    st.title("Prospector AI")
    st.caption("Sales Performance and Commission Intelligence")

    with st.sidebar:
        st.header("Navigation")
        page = st.radio("Page", ["Dashboard", "Companies"], index=0)

    if page == "Dashboard":
        render_dashboard_page()
    else:
        render_companies_page()


if __name__ == "__main__":
    main()
