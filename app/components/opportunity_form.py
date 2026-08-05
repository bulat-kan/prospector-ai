from datetime import date

import streamlit as st
from sqlalchemy import select

from app.constants import OPPORTUNITY_STAGE_CLOSED_LOST, OPPORTUNITY_STAGE_CLOSED_WON
from app.crud import CrudError, list_companies, list_company_contacts, list_company_locations
from app.database import SessionLocal
from app.form_state import set_flash_message
from app.models import Product
from app.opportunity_form_state import (
    add_product_row,
    initialize_opportunity_form_state,
    remove_product_row,
    reset_opportunity_form_state_after_success,
)
from app.opportunity_service import (
    OpportunityError,
    OpportunityProductInput,
    OpportunityValidationError,
    create_opportunity_with_products,
    normalize_opportunity_stage,
)
from app.opportunity_ui_helpers import (
    CLOSED_WON_COMMISSION_WARNING,
    INTEREST_LEVELS,
    contact_label,
    location_label,
    parse_money_input,
    stage_label,
    stage_options,
    validate_product_rows,
    validate_score_value,
)


def render_product_rows(products: tuple[Product, ...], *, prefix: str = "opportunity_product_row") -> list[dict[str, object]]:
    rows = list(st.session_state.get("opportunity_product_rows") or [])
    product_codes = [product.code for product in products]
    product_options = [None, *product_codes]
    updated_rows: list[dict[str, object]] = []

    st.caption("At least one product is required.")
    for index, row in enumerate(rows):
        with st.container(border=True):
            cols = st.columns([2, 1, 1, 1])
            current_code = row.get("product_code")
            product_index = product_options.index(current_code) if current_code in product_options else 0
            product_code = cols[0].selectbox(
                "Product *",
                product_options,
                index=product_index,
                key=f"{prefix}_{index}_product",
                format_func=lambda value: "Select product"
                if value is None
                else next(product.name for product in products if product.code == value),
            )
            quantity = cols[1].number_input(
                "Estimated quantity *",
                min_value=0,
                value=int(row.get("estimated_quantity") or 0),
                step=1,
                key=f"{prefix}_{index}_quantity",
            )
            mrr = cols[2].text_input(
                "Estimated incremental MRR",
                value=str(row.get("estimated_incremental_mrr") or "0.00"),
                key=f"{prefix}_{index}_mrr",
            )
            interest = cols[3].selectbox(
                "Interest level",
                list(INTEREST_LEVELS),
                index=list(INTEREST_LEVELS).index(str(row.get("interest_level") or "Unknown")),
                key=f"{prefix}_{index}_interest",
            )
            notes = st.text_input(
                "Product notes",
                value=str(row.get("notes") or ""),
                key=f"{prefix}_{index}_notes",
            )
            if st.button("Remove product row", key=f"{prefix}_{index}_remove"):
                remove_product_row(st.session_state, index)
                st.rerun()
            updated_rows.append(
                {
                    "product_code": product_code,
                    "estimated_quantity": int(quantity),
                    "estimated_incremental_mrr": mrr,
                    "interest_level": interest,
                    "notes": notes,
                }
            )

    st.session_state.opportunity_product_rows = updated_rows
    if st.button("Add product row", key=f"{prefix}_add"):
        add_product_row(st.session_state)
        st.rerun()
    return updated_rows


def _render_errors(errors: dict[str, str], *keys: str) -> None:
    for key in keys:
        if errors.get(key):
            st.error(errors[key])


def validate_add_opportunity_ui(rows: list[dict[str, object]]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if st.session_state.get("opportunity_company_id") is None:
        errors["company"] = "Select a company."
    if not str(st.session_state.get("opportunity_name") or "").strip():
        errors["name"] = "Opportunity name is required."

    stage = normalize_opportunity_stage(st.session_state.get("opportunity_stage"))
    if stage.value not in {OPPORTUNITY_STAGE_CLOSED_WON, OPPORTUNITY_STAGE_CLOSED_LOST}:
        if not str(st.session_state.get("opportunity_next_action") or "").strip():
            errors["next_action"] = "Next action is required for open opportunities."
        if st.session_state.get("opportunity_next_action_date") is None:
            errors["next_action_date"] = "Follow-up date is required for open opportunities."
    if stage.value == OPPORTUNITY_STAGE_CLOSED_LOST and not str(st.session_state.get("opportunity_lost_reason") or "").strip():
        errors["lost_reason"] = "Lost reason is required for Closed Lost opportunities."

    for key, label in (
        ("opportunity_internet_probability", "Internet probability"),
        ("opportunity_revenue_potential_score", "Revenue potential score"),
        ("opportunity_cross_sell_score", "Cross-sell score"),
        ("opportunity_priority_score", "Priority score"),
    ):
        error = validate_score_value(int(st.session_state.get(key) or 0), label)
        if error:
            errors[key] = error

    _, mrr_error = parse_money_input(st.session_state.get("opportunity_estimated_mrr"), "Estimated total MRR")
    if mrr_error:
        errors["estimated_mrr"] = mrr_error

    errors.update(validate_product_rows(rows))
    return errors


def render_add_opportunity_form() -> None:
    st.subheader("Add opportunity")
    initialize_opportunity_form_state(st.session_state)
    errors: dict[str, str] = st.session_state.get("opportunity_errors", {})

    try:
        with SessionLocal() as session:
            companies = list_companies(session, include_archived=False)
            products = tuple(session.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.name)).all())
            selected_company_id = st.session_state.get("opportunity_company_id")
            locations = list_company_locations(session, selected_company_id) if selected_company_id else ()
            contacts = list_company_contacts(session, selected_company_id) if selected_company_id else ()
    except CrudError as exc:
        st.error(str(exc))
        return

    company_options = [None, *(company.id for company in companies)]
    company_id = st.selectbox(
        "Company *",
        company_options,
        key="opportunity_company_id",
        format_func=lambda value: "Select company"
        if value is None
        else next(company.name for company in companies if company.id == value),
    )
    _render_errors(errors, "company")

    location_options = [None, *(location.id for location in locations)]
    if st.session_state.get("opportunity_location_id") not in location_options:
        st.session_state.opportunity_location_id = None
    contact_options = [None, *(contact.id for contact in contacts)]
    if st.session_state.get("opportunity_contact_id") not in contact_options:
        st.session_state.opportunity_contact_id = None

    cols = st.columns(2)
    cols[0].selectbox(
        "Location",
        location_options,
        key="opportunity_location_id",
        format_func=lambda value: "Unassigned"
        if value is None
        else location_label(next(location for location in locations if location.id == value)),
    )
    cols[1].selectbox(
        "Primary contact",
        contact_options,
        key="opportunity_contact_id",
        format_func=lambda value: "Unassigned"
        if value is None
        else contact_label(next(contact for contact in contacts if contact.id == value)),
    )

    st.text_input("Opportunity name *", key="opportunity_name")
    _render_errors(errors, "name")

    cols = st.columns(3)
    stage = cols[0].selectbox(
        "Stage *",
        [stage.value for stage in stage_options()],
        key="opportunity_stage",
        format_func=stage_label,
    )
    cols[1].date_input("Expected close date", value=st.session_state.get("opportunity_expected_close_date"), key="opportunity_expected_close_date")
    cols[2].text_input("Estimated total MRR", key="opportunity_estimated_mrr")
    _render_errors(errors, "estimated_mrr")

    if stage == OPPORTUNITY_STAGE_CLOSED_WON:
        st.info(CLOSED_WON_COMMISSION_WARNING)

    cols = st.columns(2)
    cols[0].text_input("Next action", key="opportunity_next_action")
    cols[1].date_input("Follow-up date", value=st.session_state.get("opportunity_next_action_date"), key="opportunity_next_action_date")
    _render_errors(errors, "next_action", "next_action_date")

    if stage == OPPORTUNITY_STAGE_CLOSED_LOST:
        st.text_area("Lost reason *", key="opportunity_lost_reason")
        _render_errors(errors, "lost_reason")
    else:
        st.text_area("Lost reason", key="opportunity_lost_reason")

    cols = st.columns(4)
    cols[0].number_input(
        "Internet probability",
        min_value=0,
        max_value=100,
        step=1,
        key="opportunity_internet_probability",
        help="Estimated likelihood that this opportunity produces an Internet sale.",
    )
    cols[1].number_input("Revenue potential score", min_value=0, max_value=100, step=1, key="opportunity_revenue_potential_score")
    cols[2].number_input("Cross-sell score", min_value=0, max_value=100, step=1, key="opportunity_cross_sell_score")
    cols[3].number_input(
        "Priority score",
        min_value=0,
        max_value=100,
        step=1,
        key="opportunity_priority_score",
        help="Overall urgency and value for follow-up.",
    )

    st.text_area("Notes", key="opportunity_notes")
    st.text_area("Score reason", key="opportunity_score_reason")

    st.markdown("**Products**")
    rows = render_product_rows(products)
    for key, message in errors.items():
        if key.startswith(("products", "product_", "quantity_", "mrr_")):
            st.error(message)

    if st.button("Create opportunity", type="primary"):
        errors = validate_add_opportunity_ui(rows)
        st.session_state.opportunity_errors = errors
        if errors:
            st.rerun()

        estimated_mrr, _ = parse_money_input(st.session_state.get("opportunity_estimated_mrr"), "Estimated total MRR")
        product_inputs = [
            OpportunityProductInput(
                product_code=str(row["product_code"]),
                estimated_quantity=int(row.get("estimated_quantity") or 0),
                estimated_incremental_mrr=parse_money_input(row.get("estimated_incremental_mrr"), "Estimated incremental MRR")[0],
                interest_level=str(row.get("interest_level") or "Unknown"),
                notes=str(row.get("notes") or ""),
            )
            for row in rows
            if row.get("product_code")
        ]
        try:
            with SessionLocal() as session:
                opportunity = create_opportunity_with_products(
                    session,
                    company_id=int(company_id),
                    location_id=st.session_state.get("opportunity_location_id"),
                    primary_contact_id=st.session_state.get("opportunity_contact_id"),
                    name=st.session_state.opportunity_name,
                    stage=stage,
                    expected_close_date=st.session_state.get("opportunity_expected_close_date"),
                    next_action=st.session_state.get("opportunity_next_action"),
                    next_action_date=st.session_state.get("opportunity_next_action_date"),
                    lost_reason=st.session_state.get("opportunity_lost_reason"),
                    estimated_mrr=estimated_mrr,
                    internet_probability=int(st.session_state.get("opportunity_internet_probability") or 0),
                    revenue_potential_score=int(st.session_state.get("opportunity_revenue_potential_score") or 0),
                    cross_sell_score=int(st.session_state.get("opportunity_cross_sell_score") or 0),
                    priority_score=int(st.session_state.get("opportunity_priority_score") or 0),
                    notes=st.session_state.get("opportunity_notes"),
                    score_reason=st.session_state.get("opportunity_score_reason"),
                    products=product_inputs,
                )
            reset_opportunity_form_state_after_success(st.session_state, opportunity.id)
            st.session_state.opportunity_errors = {}
            set_flash_message(st.session_state, f'✅ Opportunity "{opportunity.name}" added successfully.')
            st.rerun()
        except (OpportunityError, OpportunityValidationError, CrudError) as exc:
            st.session_state.opportunity_errors = {"submit": str(exc)}
            st.error(str(exc))
