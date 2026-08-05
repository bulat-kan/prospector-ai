from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.constants import (
    CLOSED_OPPORTUNITY_STAGES,
    OPEN_OPPORTUNITY_STAGES,
    OPPORTUNITY_STAGE_CLOSED_LOST,
    OPPORTUNITY_STAGE_CLOSED_WON,
    OPPORTUNITY_STAGE_LABELS,
)
from app.crud import CompanyDTO, ContactDTO, LocationDTO
from app.enums import OpportunityStage
from app.opportunity_service import OpportunitySummary, is_open_stage, money, normalize_opportunity_stage
from app.ui_helpers import format_currency
from app.validation import contact_display_name


FOLLOW_UP_ALL = "All"
FOLLOW_UP_OVERDUE = "Overdue"
FOLLOW_UP_DUE_TODAY = "Due today"
FOLLOW_UP_DUE_THIS_WEEK = "Due this week"
FOLLOW_UP_NO_DATE = "No follow-up date"
FOLLOW_UP_FUTURE = "Future"
FOLLOW_UP_FILTERS = (
    FOLLOW_UP_ALL,
    FOLLOW_UP_OVERDUE,
    FOLLOW_UP_DUE_TODAY,
    FOLLOW_UP_DUE_THIS_WEEK,
    FOLLOW_UP_NO_DATE,
    FOLLOW_UP_FUTURE,
)

INTEREST_LEVELS = ("Unknown", "Low", "Medium", "High")
CLOSED_WON_COMMISSION_WARNING = (
    "Agreement secured. Commission is not earned until qualifying services are installed "
    "or mobile lines are activated."
)
ADD_OPPORTUNITY_SUCCESS_TEMPLATE = 'Opportunity "{name}" added successfully.'


@dataclass(frozen=True)
class OpportunityFormChoices:
    companies: tuple[CompanyDTO, ...]
    locations: tuple[LocationDTO, ...]
    contacts: tuple[ContactDTO, ...]


def stage_options() -> tuple[OpportunityStage, ...]:
    return tuple(OpportunityStage(stage) for stage in OPPORTUNITY_STAGE_LABELS)


def stage_label(stage: OpportunityStage | str) -> str:
    return OPPORTUNITY_STAGE_LABELS[normalize_opportunity_stage(stage).value]


def status_label(summary: OpportunitySummary) -> str:
    if not summary.is_active:
        return "Archived"
    stage = normalize_opportunity_stage(summary.stage).value
    if stage == OPPORTUNITY_STAGE_CLOSED_WON:
        return "Closed Won"
    if stage == OPPORTUNITY_STAGE_CLOSED_LOST:
        return "Closed Lost"
    return "Open"


def is_overdue_follow_up(summary: OpportunitySummary, today: date) -> bool:
    return summary.next_action_date is not None and summary.next_action_date < today and is_open_stage(summary.stage)


def follow_up_status(summary: OpportunitySummary, today: date) -> str:
    if not is_open_stage(summary.stage):
        return "Closed"
    if summary.next_action_date is None:
        return FOLLOW_UP_NO_DATE
    if summary.next_action_date < today:
        days = (today - summary.next_action_date).days
        return f"Overdue by {days} day{'s' if days != 1 else ''}"
    if summary.next_action_date == today:
        return FOLLOW_UP_DUE_TODAY
    if summary.next_action_date <= today + timedelta(days=7):
        days = (summary.next_action_date - today).days
        return f"Due in {days} day{'s' if days != 1 else ''}"
    return FOLLOW_UP_FUTURE


def follow_up_filter_matches(summary: OpportunitySummary, filter_value: str, today: date) -> bool:
    if filter_value == FOLLOW_UP_ALL:
        return True
    if filter_value == FOLLOW_UP_OVERDUE:
        return is_overdue_follow_up(summary, today)
    if filter_value == FOLLOW_UP_DUE_TODAY:
        return is_open_stage(summary.stage) and summary.next_action_date == today
    if filter_value == FOLLOW_UP_DUE_THIS_WEEK:
        return (
            is_open_stage(summary.stage)
            and summary.next_action_date is not None
            and today < summary.next_action_date <= today + timedelta(days=7)
        )
    if filter_value == FOLLOW_UP_NO_DATE:
        return is_open_stage(summary.stage) and summary.next_action_date is None
    if filter_value == FOLLOW_UP_FUTURE:
        return (
            is_open_stage(summary.stage)
            and summary.next_action_date is not None
            and summary.next_action_date > today + timedelta(days=7)
        )
    return True


def opportunity_display_record(summary: OpportunitySummary, today: date) -> dict[str, object]:
    return {
        "Opportunity": summary.name,
        "Company": summary.company_name,
        "Location": summary.location_name or "Unassigned",
        "Primary contact": summary.primary_contact_name or "Unassigned",
        "Stage": summary.stage_display,
        "Products": ", ".join(summary.product_names),
        "Estimated quantity": summary.estimated_total_quantity,
        "Estimated MRR": format_currency(summary.estimated_mrr),
        "Internet probability": f"{summary.internet_probability}%",
        "Priority": summary.priority_score,
        "Next action": summary.next_action or "",
        "Follow-up date": summary.next_action_date.isoformat() if summary.next_action_date else "",
        "Follow-up": follow_up_status(summary, today),
        "Expected close date": summary.expected_close_date.isoformat() if summary.expected_close_date else "",
        "Status": status_label(summary),
    }


def filter_summaries(
    summaries: tuple[OpportunitySummary, ...],
    *,
    search: str = "",
    follow_up_filter: str = FOLLOW_UP_ALL,
    today: date,
) -> tuple[OpportunitySummary, ...]:
    needle = search.strip().lower()
    filtered = []
    for summary in summaries:
        if needle and needle not in summary.name.lower() and needle not in summary.company_name.lower():
            continue
        if not follow_up_filter_matches(summary, follow_up_filter, today):
            continue
        filtered.append(summary)
    return tuple(filtered)


def active_companies(companies: tuple[CompanyDTO, ...]) -> tuple[CompanyDTO, ...]:
    return tuple(company for company in companies if company.is_active)


def available_locations(company_id: Optional[int], locations: tuple[LocationDTO, ...]) -> tuple[LocationDTO, ...]:
    if company_id is None:
        return ()
    return tuple(location for location in locations if location.company_id == company_id and location.is_active)


def available_contacts(company_id: Optional[int], contacts: tuple[ContactDTO, ...]) -> tuple[ContactDTO, ...]:
    if company_id is None:
        return ()
    return tuple(contact for contact in contacts if contact.company_id == company_id and contact.is_active)


def normalize_related_selection(selected_id: Optional[int], valid_ids: set[int]) -> Optional[int]:
    return selected_id if selected_id in valid_ids else None


def location_label(location: LocationDTO) -> str:
    label = location.location_name or f"{location.address_line_1}, {location.city}"
    return f"{label} ({location.location_type.value})"


def contact_label(contact: ContactDTO) -> str:
    name = contact_display_name(contact.first_name, contact.last_name)
    if contact.job_title:
        return f"{name}, {contact.job_title}"
    return name


def validate_score_value(value: int, field_name: str) -> Optional[str]:
    if value < 0:
        return f"{field_name} must be between 0 and 100."
    if value > 100:
        return f"{field_name} must be between 0 and 100."
    return None


def parse_money_input(value: object, field_name: str) -> tuple[Optional[Decimal], Optional[str]]:
    if value in (None, ""):
        return Decimal("0.00"), None
    try:
        amount = money(value)  # type: ignore[arg-type]
    except (InvalidOperation, ValueError):
        return None, f"{field_name} must be a valid dollar amount."
    if amount < Decimal("0.00"):
        return None, f"{field_name} cannot be negative."
    return amount, None


def validate_product_rows(rows: list[dict[str, object]]) -> dict[str, str]:
    errors: dict[str, str] = {}
    selected_codes: set[str] = set()
    valid_rows = [row for row in rows if row.get("product_code")]
    if not valid_rows:
        errors["products"] = "Select at least one product."
    for index, row in enumerate(rows):
        code = str(row.get("product_code") or "")
        if not code:
            errors[f"product_{index}"] = "Select a product."
            continue
        if code in selected_codes:
            errors[f"product_{index}"] = "This product is already included in the opportunity."
        selected_codes.add(code)
        quantity = int(row.get("estimated_quantity") or 0)
        if quantity < 0:
            errors[f"quantity_{index}"] = "Estimated quantity cannot be negative."
        _, mrr_error = parse_money_input(row.get("estimated_incremental_mrr"), "Estimated incremental MRR")
        if mrr_error:
            errors[f"mrr_{index}"] = mrr_error
    return errors


def open_stage_values() -> tuple[str, ...]:
    return OPEN_OPPORTUNITY_STAGES


def closed_stage_values() -> tuple[str, ...]:
    return CLOSED_OPPORTUNITY_STAGES
