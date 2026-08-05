from datetime import date

import streamlit as st

from app.constants import OPPORTUNITY_STAGE_CLOSED_LOST, OPPORTUNITY_STAGE_CLOSED_WON
from app.crud import CrudError, RecordNotFoundError, list_company_contacts, list_company_locations
from app.database import SessionLocal
from app.form_state import set_flash_message
from app.opportunity_form_state import selected_opportunity_id, set_selected_opportunity_id
from app.opportunity_service import (
    OpportunityDetail,
    OpportunityError,
    OpportunityValidationError,
    archive_opportunity,
    get_opportunity,
    normalize_opportunity_stage,
    opportunity_to_detail,
    restore_opportunity,
    update_opportunity,
)
from app.opportunity_ui_helpers import (
    CLOSED_WON_COMMISSION_WARNING,
    contact_label,
    follow_up_status,
    location_label,
    parse_money_input,
    stage_label,
    stage_options,
    status_label,
    validate_score_value,
)
from app.ui_helpers import format_currency
from app.components.opportunity_product_editor import render_opportunity_product_editor


def load_opportunity_detail(opportunity_id: int) -> OpportunityDetail:
    with SessionLocal() as session:
        opportunity = get_opportunity(session, opportunity_id)
        return opportunity_to_detail(opportunity, today=date.today())


def render_summary(detail: OpportunityDetail) -> None:
    summary = detail.summary
    st.subheader(summary.name)
    if normalize_opportunity_stage(summary.stage).value == OPPORTUNITY_STAGE_CLOSED_WON:
        st.info(CLOSED_WON_COMMISSION_WARNING)
    if summary.is_overdue:
        st.warning(f"Follow-up is {follow_up_status(summary, date.today()).lower()}.")

    cols = st.columns(4)
    cols[0].metric("Status", status_label(summary))
    cols[1].metric("Stage", summary.stage_display)
    cols[2].metric("Estimated MRR", format_currency(summary.estimated_mrr))
    cols[3].metric("Estimated quantity", summary.estimated_total_quantity)

    cols = st.columns(4)
    cols[0].metric("Internet probability", f"{summary.internet_probability}%")
    cols[1].metric("Priority score", summary.priority_score)
    cols[2].metric("Expected close", summary.expected_close_date.isoformat() if summary.expected_close_date else "Not set")
    cols[3].metric("Follow-up", follow_up_status(summary, date.today()))

    with st.container(border=True):
        st.write(f"**Company:** {summary.company_name}")
        st.write(f"**Location:** {summary.location_name or 'Unassigned'}")
        st.write(f"**Primary contact:** {summary.primary_contact_name or 'Unassigned'}")
        st.write(f"**Next action:** {summary.next_action or 'Not set'}")
        st.write(f"**Created:** {detail.created_at.date().isoformat()}")
        st.write(f"**Updated:** {detail.updated_at.date().isoformat()}")
        if detail.notes:
            st.write(f"**Notes:** {detail.notes}")
        if detail.score_reason:
            st.write(f"**Score reason:** {detail.score_reason}")
        if detail.lost_reason:
            st.write(f"**Lost reason:** {detail.lost_reason}")


def initialize_edit_state(detail: OpportunityDetail) -> None:
    key = f"edit_opportunity_loaded_id"
    if st.session_state.get(key) == detail.summary.id:
        return
    summary = detail.summary
    st.session_state[key] = summary.id
    st.session_state.edit_opportunity_name = summary.name
    st.session_state.edit_opportunity_stage = summary.stage.value
    st.session_state.edit_opportunity_location_id = summary.location_id
    st.session_state.edit_opportunity_contact_id = summary.primary_contact_id
    st.session_state.edit_opportunity_expected_close_date = summary.expected_close_date
    st.session_state.edit_opportunity_next_action = summary.next_action or ""
    st.session_state.edit_opportunity_next_action_date = summary.next_action_date
    st.session_state.edit_opportunity_lost_reason = detail.lost_reason or ""
    st.session_state.edit_opportunity_estimated_mrr = f"{summary.estimated_mrr:.2f}" if summary.estimated_mrr is not None else "0.00"
    st.session_state.edit_opportunity_internet_probability = summary.internet_probability
    st.session_state.edit_opportunity_revenue_potential_score = detail.revenue_potential_score
    st.session_state.edit_opportunity_cross_sell_score = detail.cross_sell_score
    st.session_state.edit_opportunity_priority_score = summary.priority_score
    st.session_state.edit_opportunity_notes = detail.notes or ""
    st.session_state.edit_opportunity_score_reason = detail.score_reason or ""


def render_edit_form(detail: OpportunityDetail) -> None:
    initialize_edit_state(detail)
    summary = detail.summary
    with st.expander("Edit opportunity"):
        st.caption("Company cannot be changed after opportunity creation in this version.")
        st.text_input("Company", value=summary.company_name, disabled=True, key=f"edit_opportunity_company_{summary.id}")

        with SessionLocal() as session:
            locations = list_company_locations(session, summary.company_id)
            contacts = list_company_contacts(session, summary.company_id)

        location_ids = [None, *(location.id for location in locations)]
        if st.session_state.get("edit_opportunity_location_id") not in location_ids:
            location_ids.append(st.session_state.get("edit_opportunity_location_id"))
        contact_ids = [None, *(contact.id for contact in contacts)]
        if st.session_state.get("edit_opportunity_contact_id") not in contact_ids:
            contact_ids.append(st.session_state.get("edit_opportunity_contact_id"))

        def edit_location_label(value):
            if value is None:
                return "Unassigned"
            location = next((location for location in locations if location.id == value), None)
            return location_label(location) if location is not None else "Inactive or unavailable location"

        def edit_contact_label(value):
            if value is None:
                return "Unassigned"
            contact = next((contact for contact in contacts if contact.id == value), None)
            return contact_label(contact) if contact is not None else "Inactive or unavailable contact"

        st.text_input("Opportunity name *", key="edit_opportunity_name")
        cols = st.columns(3)
        stage = cols[0].selectbox(
            "Stage *",
            [stage.value for stage in stage_options()],
            key="edit_opportunity_stage",
            format_func=stage_label,
        )
        cols[1].selectbox(
            "Location",
            location_ids,
            key="edit_opportunity_location_id",
            format_func=edit_location_label,
        )
        cols[2].selectbox(
            "Primary contact",
            contact_ids,
            key="edit_opportunity_contact_id",
            format_func=edit_contact_label,
        )
        if stage == OPPORTUNITY_STAGE_CLOSED_WON:
            st.info(CLOSED_WON_COMMISSION_WARNING)

        cols = st.columns(3)
        cols[0].date_input("Expected close date", value=st.session_state.get("edit_opportunity_expected_close_date"), key="edit_opportunity_expected_close_date")
        cols[1].text_input("Estimated total MRR", key="edit_opportunity_estimated_mrr")
        cols[2].date_input("Follow-up date", value=st.session_state.get("edit_opportunity_next_action_date"), key="edit_opportunity_next_action_date")
        st.text_input("Next action", key="edit_opportunity_next_action")
        st.text_area("Lost reason", key="edit_opportunity_lost_reason")

        cols = st.columns(4)
        cols[0].number_input("Internet probability", min_value=0, max_value=100, step=1, key="edit_opportunity_internet_probability")
        cols[1].number_input("Revenue potential score", min_value=0, max_value=100, step=1, key="edit_opportunity_revenue_potential_score")
        cols[2].number_input("Cross-sell score", min_value=0, max_value=100, step=1, key="edit_opportunity_cross_sell_score")
        cols[3].number_input("Priority score", min_value=0, max_value=100, step=1, key="edit_opportunity_priority_score")
        st.text_area("Notes", key="edit_opportunity_notes")
        st.text_area("Score reason", key="edit_opportunity_score_reason")

        if st.button("Save opportunity", type="primary"):
            errors = []
            if not st.session_state.edit_opportunity_name.strip():
                errors.append("Opportunity name is required.")
            stage_value = normalize_opportunity_stage(stage).value
            if stage_value not in {OPPORTUNITY_STAGE_CLOSED_WON, OPPORTUNITY_STAGE_CLOSED_LOST}:
                if not st.session_state.edit_opportunity_next_action.strip():
                    errors.append("Next action is required for open opportunities.")
                if st.session_state.edit_opportunity_next_action_date is None:
                    errors.append("Follow-up date is required for open opportunities.")
            if stage_value == OPPORTUNITY_STAGE_CLOSED_LOST and not st.session_state.edit_opportunity_lost_reason.strip():
                errors.append("Lost reason is required for Closed Lost opportunities.")
            for key, label in (
                ("edit_opportunity_internet_probability", "Internet probability"),
                ("edit_opportunity_revenue_potential_score", "Revenue potential score"),
                ("edit_opportunity_cross_sell_score", "Cross-sell score"),
                ("edit_opportunity_priority_score", "Priority score"),
            ):
                error = validate_score_value(int(st.session_state.get(key) or 0), label)
                if error:
                    errors.append(error)
            estimated_mrr, mrr_error = parse_money_input(st.session_state.edit_opportunity_estimated_mrr, "Estimated total MRR")
            if mrr_error:
                errors.append(mrr_error)
            if errors:
                for error in errors:
                    st.error(error)
                return
            try:
                with SessionLocal() as session:
                    update_opportunity(
                        session,
                        summary.id,
                        name=st.session_state.edit_opportunity_name,
                        stage=stage,
                        location_id=st.session_state.get("edit_opportunity_location_id"),
                        primary_contact_id=st.session_state.get("edit_opportunity_contact_id"),
                        expected_close_date=st.session_state.get("edit_opportunity_expected_close_date"),
                        next_action=st.session_state.get("edit_opportunity_next_action"),
                        next_action_date=st.session_state.get("edit_opportunity_next_action_date"),
                        lost_reason=st.session_state.get("edit_opportunity_lost_reason"),
                        estimated_mrr=estimated_mrr,
                        internet_probability=int(st.session_state.get("edit_opportunity_internet_probability") or 0),
                        revenue_potential_score=int(st.session_state.get("edit_opportunity_revenue_potential_score") or 0),
                        cross_sell_score=int(st.session_state.get("edit_opportunity_cross_sell_score") or 0),
                        priority_score=int(st.session_state.get("edit_opportunity_priority_score") or 0),
                        notes=st.session_state.get("edit_opportunity_notes"),
                        score_reason=st.session_state.get("edit_opportunity_score_reason"),
                    )
                st.session_state.edit_opportunity_loaded_id = None
                set_flash_message(st.session_state, "✅ Opportunity updated successfully.")
                st.rerun()
            except (OpportunityError, OpportunityValidationError, CrudError) as exc:
                st.error(str(exc))


def render_archive_controls(detail: OpportunityDetail) -> None:
    summary = detail.summary
    with st.container(border=True):
        if summary.is_active:
            if not st.session_state.get(f"confirm_archive_opportunity_{summary.id}"):
                if st.button("Archive opportunity"):
                    st.session_state[f"confirm_archive_opportunity_{summary.id}"] = True
                    st.rerun()
            else:
                st.warning("Confirm archiving this opportunity.")
                if st.button("Confirm archive", type="primary"):
                    with SessionLocal() as session:
                        archive_opportunity(session, summary.id)
                    st.session_state[f"confirm_archive_opportunity_{summary.id}"] = False
                    set_flash_message(st.session_state, f'✅ Opportunity "{summary.name}" archived successfully.')
                    st.rerun()
                if st.button("Cancel archive"):
                    st.session_state[f"confirm_archive_opportunity_{summary.id}"] = False
                    st.rerun()
        else:
            if st.button("Restore opportunity", type="primary"):
                with SessionLocal() as session:
                    restore_opportunity(session, summary.id)
                set_flash_message(st.session_state, f'✅ Opportunity "{summary.name}" restored successfully.')
                st.rerun()


def render_opportunity_detail() -> None:
    opportunity_id = selected_opportunity_id(st.session_state)
    if opportunity_id is None:
        st.info("Select an opportunity to open its detail view.")
        return
    try:
        detail = load_opportunity_detail(opportunity_id)
    except RecordNotFoundError:
        set_selected_opportunity_id(st.session_state, None)
        st.info("The selected opportunity no longer exists.")
        return
    except (OpportunityError, CrudError) as exc:
        st.error(str(exc))
        return

    render_summary(detail)
    render_edit_form(detail)
    render_opportunity_product_editor(detail.summary.id, detail.products)
    render_archive_controls(detail)
