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
from app.form_state import (
    contact_form_key,
    initialize_add_company_form_state,
    initialize_contact_form_state,
    pop_flash_message,
    reset_add_company_form_state,
    reset_contact_form_state,
    set_flash_message,
    validate_add_company_form_state,
    validate_contact_form_state,
)
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
from app.validation import (
    CONTACT_TITLE_OPTIONS,
    CONTACT_TITLE_OTHER,
    CONTACT_TITLE_PLACEHOLDER,
    INDUSTRY_OPTIONS,
    INDUSTRY_OTHER,
    INDUSTRY_PLACEHOLDER,
    LOCATION_TYPE_OPTIONS,
    STATE_OPTIONS,
    format_us_phone,
    state_display_label,
    title_selection_for_existing,
    contact_display_name,
)


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


def render_flash_message() -> None:
    flash = pop_flash_message(st.session_state)
    if flash is None:
        return
    message, level = flash
    if level == "success":
        st.success(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.error(message)


def company_options(search: str = ""):
    with SessionLocal() as session:
        return list_companies(session, search=search)


def lead_source_options() -> list[Optional[str]]:
    return [None, LEAD_SOURCE_AE_FOUND, LEAD_SOURCE_REFERRAL]


def lead_source_label(value: Optional[str]) -> str:
    if value is None:
        return "Not set"
    return LEAD_SOURCE_LABELS.get(value, friendly_label(value))


def contact_name_label(first_name: Optional[str], last_name: Optional[str]) -> str:
    return contact_display_name(first_name, last_name)


def decision_role_label(value: ContactRole) -> str:
    return friendly_label(value)


def decision_role_value_label(value: str) -> str:
    return friendly_label(ContactRole(value))


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
    if st.session_state.get("add_company_reset_pending"):
        reset_add_company_form_state(st.session_state)
        st.session_state.add_company_reset_pending = False
    initialize_add_company_form_state(st.session_state)
    if st.session_state.get("add_company_success"):
        st.success(st.session_state.add_company_success)
        st.session_state.add_company_success = ""

    errors = st.session_state.get("add_company_errors", {})
    if errors.get("submit"):
        st.error(errors["submit"])
    st.caption("* Required fields")
    st.text_input("Company name *", placeholder="Acme Services LLC", key="add_company_name")
    if errors.get("name"):
        st.error(errors["name"])

    cols = st.columns(2)
    cols[0].text_input("Public phone", key="add_company_phone", max_chars=10)
    if st.session_state.add_company_phone and st.session_state.add_company_phone.isdigit() and len(st.session_state.add_company_phone) == 10:
        cols[0].caption(format_us_phone(st.session_state.add_company_phone))
    cols[1].text_input("Website", key="add_company_website", placeholder="example.com")
    if errors.get("phone"):
        cols[0].error(errors["phone"])
    if errors.get("website"):
        cols[1].error(errors["website"])

    industry = cols[0].selectbox(
        "Industry *",
        list(INDUSTRY_OPTIONS),
        key="add_company_industry",
    )
    if industry == INDUSTRY_OTHER:
        cols[0].text_input("Other industry *", key="add_company_other_industry")
    lead_source = cols[1].selectbox(
        "Lead source *",
        lead_source_options(),
        key="add_company_lead_source",
        format_func=lead_source_label,
    )
    if errors.get("industry"):
        cols[0].error(errors["industry"])
    if errors.get("lead_source"):
        cols[1].error(errors["lead_source"])

    if lead_source == LEAD_SOURCE_REFERRAL:
        with st.container(border=True):
            st.subheader("Referral partner *")
            st.radio(
                "Referral option",
                ["Select existing referral partner", "Add new referral partner"],
                key="add_company_referral_mode",
            )
            if st.session_state.add_company_referral_mode == "Select existing referral partner":
                partners = referral_partner_options()
                partner_options = [None] + [partner.id for partner in partners]
                partner_lookup = {partner.id: partner for partner in partners}
                st.selectbox(
                    "Existing referral partner *",
                    partner_options,
                    key="add_company_referral_partner_id",
                    format_func=lambda partner_id: "Select partner" if partner_id is None else partner_lookup[partner_id].display_name,
                )
            else:
                partner_cols = st.columns(2)
                partner_cols[0].text_input("First name", key="add_company_partner_first")
                partner_cols[1].text_input("Last name", key="add_company_partner_last")
                partner_cols[0].text_input("Organization", key="add_company_partner_org")
                partner_cols[1].text_input("Role / type", key="add_company_partner_role")
                partner_cols[0].text_input("Phone", key="add_company_partner_phone")
                partner_cols[1].text_input("Email", key="add_company_partner_email")
                st.checkbox("Registered Spectrum referral partner", key="add_company_partner_registered")
                st.text_input("Spectrum partner reference", key="add_company_partner_reference")
                st.text_area("Referral partner notes", key="add_company_partner_notes")
            if errors.get("referral"):
                st.error(errors["referral"])

    st.text_area("Notes", key="add_company_notes")
    submitted = st.button("Create company", type="primary")
    if submitted:
        company_payload, partner_payload, errors = validate_add_company_form_state(st.session_state)
        st.session_state.add_company_errors = errors
        if errors:
            st.rerun()
        try:
            with SessionLocal() as session:
                if partner_payload is not None:
                    partner = create_referral_partner(session, **partner_payload)
                    company_payload["referral_partner_id"] = partner.id
                company = create_company(session, **company_payload)
            st.session_state.selected_company_id = company.id
            st.session_state.add_company_success = f"Created {company.name}."
            st.session_state.add_company_errors = {}
            st.session_state.add_company_reset_pending = True
            st.rerun()
        except (CrudError, DuplicateRecordError, ValidationError) as exc:
            st.session_state.add_company_errors = {"submit": str(exc)}
            st.error(str(exc))


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
                    set_flash_message(st.session_state, "Company archived.")
                    st.rerun()
                except CrudError as exc:
                    show_crud_message(exc)
        else:
            if st.button("Restore company"):
                try:
                    with SessionLocal() as session:
                        restore_company(session, company.id)
                    set_flash_message(st.session_state, "Company restored.")
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
        with st.form(f"add_location_{company_id}"):
            address_line_1 = st.text_input("Street address *")
            address_line_2 = st.text_input("Suite / Unit")
            cols = st.columns(3)
            city = cols[0].text_input("City *")
            state_options = [None] + list(STATE_OPTIONS)
            state = cols[1].selectbox(
                "State *",
                state_options,
                format_func=lambda value: "Select state" if value is None else state_display_label(value),
            )
            postal_code = cols[2].text_input("ZIP code *", max_chars=5)
            location_type_options = [None] + list(LOCATION_TYPE_OPTIONS)
            location_type = st.selectbox(
                "Location type *",
                location_type_options,
                format_func=lambda value: "Select location type" if value is None else value.value,
            )
            location_name = st.text_input("Location label (optional)")
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
                location = create_location(
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
            set_flash_message(st.session_state, f'✅ Location "{location.location_name or "Location"}" added successfully.')
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
                state_options = list(STATE_OPTIONS)
                state_index = state_options.index(selected.state) if selected.state in state_options else state_options.index("FL")
                state = cols[1].selectbox(
                    "State *",
                    state_options,
                    index=state_index,
                    format_func=state_display_label,
                )
                postal_code = cols[2].text_input("ZIP code *", value=selected.postal_code, max_chars=5)
                location_type = st.selectbox(
                    "Location type *",
                    list(LOCATION_TYPE_OPTIONS),
                    index=list(LOCATION_TYPE_OPTIONS).index(selected.location_type)
                    if selected.location_type in LOCATION_TYPE_OPTIONS
                    else 0,
                    format_func=lambda value: value.value,
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
                    location = update_location(
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
                set_flash_message(st.session_state, f'✅ Location "{location.location_name or "Location"}" updated successfully.')
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
                            location = deactivate_location(session, selected.id, reason)
                        set_flash_message(st.session_state, f'✅ Location "{location.location_name or "Location"}" marked inactive.')
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)
            else:
                if st.button("Restore location"):
                    try:
                        with SessionLocal() as session:
                            location = restore_location(session, selected.id)
                        set_flash_message(st.session_state, f'✅ Location "{location.location_name or "Location"}" restored successfully.')
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)


def render_contacts_tab(company_id: int) -> None:
    try:
        with SessionLocal() as session:
            include_inactive = st.toggle("Show inactive contacts", value=False, key=f"show_inactive_contacts_{company_id}")
            contacts = list_company_contacts(session, company_id, include_inactive=include_inactive)
            locations = list_company_locations(session, company_id, include_inactive=True)
    except CrudError as exc:
        show_crud_message(exc)
        return
    location_lookup = {
        location.id: f"{location.location_name or location.address_line_1}{' (inactive)' if not location.is_active else ''}"
        for location in locations
    }
    rows = [
        {
            "Name": contact_name_label(contact.first_name, contact.last_name),
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
        (
            f"{location.location_name or location.address_line_1}{' (inactive)' if not location.is_active else ''}"
            for location in locations
            if location.id == location_id
        ),
        str(location_id),
    )

    with st.expander("Add contact", expanded=False):
        add_prefix = f"add_contact_{company_id}"
        if st.session_state.get(f"{add_prefix}_reset_pending"):
            reset_contact_form_state(st.session_state, add_prefix)
            st.session_state[f"{add_prefix}_reset_pending"] = False
        initialize_contact_form_state(st.session_state, add_prefix)
        add_errors = st.session_state.get(f"{add_prefix}_errors", {})
        with st.form(f"add_contact_form_{company_id}"):
            st.caption("At least a first name or last name is required.")
            cols = st.columns(2)
            cols[0].text_input("First name", key=contact_form_key(add_prefix, "first_name"))
            cols[1].text_input("Last name", key=contact_form_key(add_prefix, "last_name"))
            if add_errors.get("name"):
                st.error(add_errors["name"])
            title_selection = cols[0].selectbox(
                "Title",
                list(CONTACT_TITLE_OPTIONS),
                key=contact_form_key(add_prefix, "title_selection"),
            )
            if title_selection == CONTACT_TITLE_OTHER:
                cols[0].text_input("Other title", key=contact_form_key(add_prefix, "other_title"))
                if add_errors.get("title"):
                    cols[0].error(add_errors["title"])
            current_location = st.session_state.get(contact_form_key(add_prefix, "location_id"))
            location_index = location_options.index(current_location) if current_location in location_options else 0
            cols[1].selectbox(
                "Assigned location",
                location_options,
                index=location_index,
                format_func=location_label,
                key=contact_form_key(add_prefix, "location_id"),
            )
            cols[0].text_input("Phone", key=contact_form_key(add_prefix, "phone"), max_chars=10)
            phone_value = st.session_state.get(contact_form_key(add_prefix, "phone"))
            if phone_value and str(phone_value).isdigit() and len(str(phone_value)) == 10:
                cols[0].caption(format_phone(str(phone_value)))
            if add_errors.get("phone"):
                cols[0].error(add_errors["phone"])
            cols[1].text_input("Email", key=contact_form_key(add_prefix, "email"))
            if add_errors.get("email"):
                cols[1].error(add_errors["email"])
            role_values = [role.value for role in ContactRole]
            role_current = st.session_state.get(contact_form_key(add_prefix, "decision_role"), ContactRole.UNKNOWN.value)
            role_index = role_values.index(str(role_current)) if str(role_current) in role_values else 0
            st.selectbox(
                "Decision role *",
                role_values,
                index=role_index,
                format_func=decision_role_value_label,
                key=contact_form_key(add_prefix, "decision_role"),
            )
            if add_errors.get("decision_role"):
                st.error(add_errors["decision_role"])
            st.checkbox("Primary contact", key=contact_form_key(add_prefix, "is_primary_contact"))
            st.text_area("Notes", key=contact_form_key(add_prefix, "notes"))
            submitted = st.form_submit_button("Add contact", type="primary")
    if submitted:
        payload, errors = validate_contact_form_state(st.session_state, add_prefix)
        st.session_state[f"{add_prefix}_errors"] = errors
        if errors:
            st.rerun()
        try:
            with SessionLocal() as session:
                create_contact(
                    session,
                    company_id=company_id,
                    location_id=payload["location_id"],
                    first_name=payload["first_name"],
                    last_name=payload["last_name"],
                    job_title=payload["job_title"],
                    phone=payload["phone"],
                    email=payload["email"],
                    decision_role=payload["decision_role"],
                    is_primary_contact=bool(payload["is_primary_contact"]),
                    notes=payload["notes"],
                )
            name = contact_name_label(payload.get("first_name"), payload.get("last_name"))
            st.session_state[f"{add_prefix}_errors"] = {}
            st.session_state[f"{add_prefix}_reset_pending"] = True
            set_flash_message(st.session_state, f'✅ Contact "{name}" added successfully.')
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
            edit_prefix = f"edit_contact_{selected.id}"
            initialize_contact_form_state(
                st.session_state,
                edit_prefix,
                {
                    "first_name": selected.first_name or "",
                    "last_name": selected.last_name or "",
                    "title_selection": title_selection_for_existing(selected.job_title)[0],
                    "other_title": title_selection_for_existing(selected.job_title)[1],
                    "location_id": selected.location_id,
                    "phone": selected.phone or "",
                    "email": selected.email or "",
                    "decision_role": selected.decision_role.value,
                    "is_primary_contact": selected.is_primary_contact,
                    "notes": selected.notes or "",
                },
            )
            edit_errors = st.session_state.get(f"{edit_prefix}_errors", {})
            with st.form(f"edit_contact_form_{selected.id}"):
                st.caption("At least a first name or last name is required.")
                cols = st.columns(2)
                cols[0].text_input("First name", key=contact_form_key(edit_prefix, "first_name"))
                cols[1].text_input("Last name", key=contact_form_key(edit_prefix, "last_name"))
                if edit_errors.get("name"):
                    st.error(edit_errors["name"])
                edit_title_selection = cols[0].selectbox(
                    "Title",
                    list(CONTACT_TITLE_OPTIONS),
                    key=contact_form_key(edit_prefix, "title_selection"),
                )
                if edit_title_selection == CONTACT_TITLE_OTHER:
                    cols[0].text_input("Other title", key=contact_form_key(edit_prefix, "other_title"))
                    if edit_errors.get("title"):
                        cols[0].error(edit_errors["title"])
                current_location = st.session_state.get(contact_form_key(edit_prefix, "location_id"))
                location_index = location_options.index(current_location) if current_location in location_options else 0
                cols[1].selectbox(
                    "Assigned location",
                    location_options,
                    index=location_index,
                    format_func=location_label,
                    key=contact_form_key(edit_prefix, "location_id"),
                )
                cols[0].text_input("Phone", key=contact_form_key(edit_prefix, "phone"), max_chars=10)
                edit_phone_value = st.session_state.get(contact_form_key(edit_prefix, "phone"))
                if edit_phone_value and str(edit_phone_value).isdigit() and len(str(edit_phone_value)) == 10:
                    cols[0].caption(format_phone(str(edit_phone_value)))
                if edit_errors.get("phone"):
                    cols[0].error(edit_errors["phone"])
                cols[1].text_input("Email", key=contact_form_key(edit_prefix, "email"))
                if edit_errors.get("email"):
                    cols[1].error(edit_errors["email"])
                role_values = [role.value for role in ContactRole]
                edit_role_current = st.session_state.get(contact_form_key(edit_prefix, "decision_role"), ContactRole.UNKNOWN)
                edit_role_value = edit_role_current.value if isinstance(edit_role_current, ContactRole) else str(edit_role_current)
                edit_role_index = role_values.index(edit_role_value) if edit_role_value in role_values else 0
                st.selectbox(
                    "Decision role *",
                    role_values,
                    index=edit_role_index,
                    format_func=decision_role_value_label,
                    key=contact_form_key(edit_prefix, "decision_role"),
                )
                if edit_errors.get("decision_role"):
                    st.error(edit_errors["decision_role"])
                st.checkbox("Primary contact", key=contact_form_key(edit_prefix, "is_primary_contact"))
                st.text_area("Notes", key=contact_form_key(edit_prefix, "notes"))
                submitted = st.form_submit_button("Save contact", type="primary")
        if submitted:
            payload, errors = validate_contact_form_state(st.session_state, edit_prefix)
            st.session_state[f"{edit_prefix}_errors"] = errors
            if errors:
                st.rerun()
            try:
                with SessionLocal() as session:
                    update_contact(
                        session,
                        selected.id,
                        location_id=payload["location_id"],
                        first_name=payload["first_name"],
                        last_name=payload["last_name"],
                        job_title=payload["job_title"],
                        phone=payload["phone"],
                        email=payload["email"],
                        decision_role=payload["decision_role"],
                        is_primary_contact=bool(payload["is_primary_contact"]),
                        notes=payload["notes"],
                    )
                name = contact_name_label(payload.get("first_name"), payload.get("last_name"))
                st.session_state[f"{edit_prefix}_errors"] = {}
                set_flash_message(st.session_state, f'✅ Contact "{name}" updated successfully.')
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
                        set_flash_message(
                            st.session_state,
                            f'✅ Contact "{contact_name_label(selected.first_name, selected.last_name)}" marked as no longer with the company.',
                        )
                        st.rerun()
                    except CrudError as exc:
                        show_crud_message(exc)
            else:
                if st.button("Restore contact"):
                    try:
                        with SessionLocal() as session:
                            restore_contact(session, selected.id)
                        set_flash_message(
                            st.session_state,
                            f'✅ Contact "{contact_name_label(selected.first_name, selected.last_name)}" restored successfully.',
                        )
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
    render_flash_message()
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
