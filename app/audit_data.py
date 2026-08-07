import sys
from dataclasses import dataclass

from sqlalchemy import select, text

from app.database import SessionLocal
from app.models import Location
from app.order_service import OrderValidationError, normalize_order_status
from app.opportunity_service import OpportunityValidationError, is_open_stage, normalize_opportunity_stage
from app.validation import (
    normalize_city,
    normalize_company_phone,
    normalize_contact_phone,
    normalize_email,
    normalize_phone,
    normalize_website,
    normalize_zip_code,
    validate_referral_partner_identity,
    validate_lead_source,
    validate_location_type,
    validate_us_state,
    validate_decision_role,
)


@dataclass(frozen=True)
class AuditIssue:
    category: str
    message: str


def _check(callable_obj, message: str, issues: list[AuditIssue], category: str) -> None:
    try:
        callable_obj()
    except ValueError:
        issues.append(AuditIssue(category, message))


def audit_contacts(session) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    location_ids = set(session.scalars(select(Location.id)).all())
    rows = session.execute(
        text("SELECT id, first_name, last_name, email, phone, decision_role, job_title, location_id FROM contacts ORDER BY id")
    ).mappings()
    for contact in rows:
        if not (contact["first_name"] or contact["last_name"]):
            issues.append(AuditIssue("Contacts", f"Contact ID {contact['id']}: missing first and last name"))
        if contact["email"]:
            _check(lambda value=contact["email"]: normalize_email(value), f'Contact ID {contact["id"]}: invalid email "{contact["email"]}"', issues, "Contacts")
        if contact["phone"]:
            _check(lambda value=contact["phone"]: normalize_contact_phone(value), f'Contact ID {contact["id"]}: invalid phone "{contact["phone"]}"', issues, "Contacts")
        _check(lambda value=contact["decision_role"]: validate_decision_role(value), f"Contact ID {contact['id']}: unsupported decision role", issues, "Contacts")
        if contact["job_title"] is not None and not contact["job_title"].strip():
            issues.append(AuditIssue("Contacts", f"Contact ID {contact['id']}: title contains only whitespace"))
        if contact["location_id"] is not None and contact["location_id"] not in location_ids:
            issues.append(AuditIssue("Contacts", f"Contact ID {contact['id']}: assigned to nonexistent location {contact['location_id']}"))
    return issues


def audit_locations(session) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    rows = session.execute(text("SELECT id, postal_code, state, location_type, location_name, city FROM locations ORDER BY id")).mappings()
    for location in rows:
        _check(lambda value=location["postal_code"]: normalize_zip_code(value), f'Location ID {location["id"]}: invalid ZIP "{location["postal_code"]}"', issues, "Locations")
        _check(lambda value=location["state"]: validate_us_state(value), f'Location ID {location["id"]}: invalid state "{location["state"]}"', issues, "Locations")
        _check(lambda value=location["location_type"]: validate_location_type(value), f"Location ID {location['id']}: invalid location type {location['location_type']}", issues, "Locations")
        if not (location["location_name"] and location["location_name"].strip()):
            issues.append(AuditIssue("Locations", f"Location ID {location['id']}: missing or blank label"))
        try:
            normalized_city = normalize_city(location["city"])
            if normalized_city != location["city"]:
                issues.append(AuditIssue("Locations", f'Location ID {location["id"]}: city requires normalization "{location["city"]}"'))
        except OpportunityValidationError:
            issues.append(AuditIssue("Locations", f"Location ID {location['id']}: city is required"))
    return issues


def audit_companies(session) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    rows = session.execute(text("SELECT id, main_phone, website, lead_source FROM companies ORDER BY id")).mappings()
    for company in rows:
        if company["main_phone"]:
            _check(lambda value=company["main_phone"]: normalize_company_phone(value), f'Company ID {company["id"]}: invalid public phone "{company["main_phone"]}"', issues, "Companies")
        if company["website"]:
            _check(lambda value=company["website"]: normalize_website(value), f'Company ID {company["id"]}: invalid website "{company["website"]}"', issues, "Companies")
        if company["lead_source"]:
            _check(lambda value=company["lead_source"]: validate_lead_source(value), f'Company ID {company["id"]}: unsupported lead source "{company["lead_source"]}"', issues, "Companies")
    return issues


def audit_referral_partners(session) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    rows = session.execute(
        text(
            "SELECT id, first_name, last_name, organization, phone, email, source_system, external_id "
            "FROM referral_partners ORDER BY id"
        )
    ).mappings()
    for partner in rows:
        for field_name in ("first_name", "last_name", "organization"):
            value = partner[field_name]
            if value is not None and not value.strip():
                issues.append(
                    AuditIssue(
                        "Referral Partners",
                        f"Referral Partner ID {partner['id']}: {field_name} contains only whitespace",
                    )
                )
        _check(
            lambda row=partner: validate_referral_partner_identity(
                row["first_name"],
                row["last_name"],
                row["organization"],
                row["phone"],
                row["email"],
            ),
            f"Referral Partner ID {partner['id']}: missing identity",
            issues,
            "Referral Partners",
        )
        if partner["phone"]:
            _check(
                lambda value=partner["phone"]: normalize_phone(value, field_name="Referral partner phone"),
                f'Referral Partner ID {partner["id"]}: invalid phone "{partner["phone"]}"',
                issues,
                "Referral Partners",
            )
        if partner["email"]:
            _check(
                lambda value=partner["email"]: normalize_email(value),
                f'Referral Partner ID {partner["id"]}: invalid email "{partner["email"]}"',
                issues,
                "Referral Partners",
            )
        if bool(partner["source_system"]) != bool(partner["external_id"]):
            issues.append(
                AuditIssue(
                    "Referral Partners",
                    f"Referral Partner ID {partner['id']}: source_system and external_id must be provided together",
                )
            )
    return issues


def audit_opportunities(session) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    rows = session.execute(
        text(
            "SELECT o.id, o.company_id, o.location_id, o.primary_contact_id, o.stage, "
            "o.next_action, o.next_action_date, o.lost_reason, o.internet_probability, "
            "o.revenue_potential_score, o.cross_sell_score, o.priority_score, o.estimated_mrr, "
            "c.id AS company_exists, l.company_id AS location_company_id, ct.company_id AS contact_company_id "
            "FROM opportunities o "
            "LEFT JOIN companies c ON c.id = o.company_id "
            "LEFT JOIN locations l ON l.id = o.location_id "
            "LEFT JOIN contacts ct ON ct.id = o.primary_contact_id "
            "ORDER BY o.id"
        )
    ).mappings()
    for opportunity in rows:
        if opportunity["company_exists"] is None:
            issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: missing company {opportunity['company_id']}"))
        if opportunity["location_id"] is not None:
            if opportunity["location_company_id"] is None:
                issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: missing location {opportunity['location_id']}"))
            elif opportunity["location_company_id"] != opportunity["company_id"]:
                issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: location belongs to another company"))
        if opportunity["primary_contact_id"] is not None:
            if opportunity["contact_company_id"] is None:
                issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: missing contact {opportunity['primary_contact_id']}"))
            elif opportunity["contact_company_id"] != opportunity["company_id"]:
                issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: contact belongs to another company"))
        try:
            stage = normalize_opportunity_stage(opportunity["stage"])
            if is_open_stage(stage):
                if not (opportunity["next_action"] and opportunity["next_action"].strip()):
                    issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: open opportunity missing next_action"))
                if opportunity["next_action_date"] is None:
                    issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: open opportunity missing next_action_date"))
            if stage.value == "CLOSED_LOST" and not (opportunity["lost_reason"] and opportunity["lost_reason"].strip()):
                issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: Closed Lost missing lost_reason"))
        except ValueError:
            issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: invalid stage {opportunity['stage']}"))
        for field_name in ("internet_probability", "revenue_potential_score", "cross_sell_score", "priority_score"):
            score = opportunity[field_name]
            if score is not None and (score < 0 or score > 100):
                issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: {field_name} outside 0-100"))
        if opportunity["estimated_mrr"] is not None and opportunity["estimated_mrr"] < 0:
            issues.append(AuditIssue("Opportunities", f"Opportunity ID {opportunity['id']}: negative estimated MRR"))

    product_rows = session.execute(
        text(
            "SELECT op.id, op.opportunity_id, op.product_id, op.product_code, op.estimated_quantity, "
            "op.estimated_incremental_mrr, p.id AS product_exists "
            "FROM opportunity_products op "
            "LEFT JOIN products p ON p.id = op.product_id "
            "ORDER BY op.id"
        )
    ).mappings()
    for row in product_rows:
        if row["product_id"] is None or row["product_exists"] is None:
            issues.append(AuditIssue("Opportunities", f"OpportunityProduct ID {row['id']}: missing product"))
        if row["estimated_quantity"] is not None and row["estimated_quantity"] < 0:
            issues.append(AuditIssue("Opportunities", f"OpportunityProduct ID {row['id']}: negative quantity"))
        if row["estimated_incremental_mrr"] is not None and row["estimated_incremental_mrr"] < 0:
            issues.append(AuditIssue("Opportunities", f"OpportunityProduct ID {row['id']}: negative product MRR"))

    duplicates = session.execute(
        text(
            "SELECT opportunity_id, product_code, COUNT(*) AS row_count "
            "FROM opportunity_products "
            "GROUP BY opportunity_id, product_code HAVING COUNT(*) > 1"
        )
    ).mappings()
    for duplicate in duplicates:
        issues.append(
            AuditIssue(
                "Opportunities",
                f"Opportunity ID {duplicate['opportunity_id']}: duplicate product rows for {duplicate['product_code']}",
            )
        )
    return issues


def audit_orders(session) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    rows = session.execute(
        text(
            "SELECT s.id, s.company_id, s.location_id, s.contact_id, s.opportunity_id, s.status, "
            "s.order_date, s.external_order_number, c.id AS company_exists, "
            "l.company_id AS location_company_id, ct.company_id AS contact_company_id, "
            "o.company_id AS opportunity_company_id "
            "FROM sales s "
            "LEFT JOIN companies c ON c.id = s.company_id "
            "LEFT JOIN locations l ON l.id = s.location_id "
            "LEFT JOIN contacts ct ON ct.id = s.contact_id "
            "LEFT JOIN opportunities o ON o.id = s.opportunity_id "
            "ORDER BY s.id"
        )
    ).mappings()
    for order in rows:
        if order["company_exists"] is None:
            issues.append(AuditIssue("Orders", f"Order ID {order['id']}: missing company {order['company_id']}"))
        if order["order_date"] is None:
            issues.append(AuditIssue("Orders", f"Order ID {order['id']}: missing order date"))
        try:
            normalize_order_status(order["status"])
        except OrderValidationError:
            issues.append(AuditIssue("Orders", f"Order ID {order['id']}: invalid status {order['status']}"))
        if order["location_id"] is not None:
            if order["location_company_id"] is None:
                issues.append(AuditIssue("Orders", f"Order ID {order['id']}: missing location {order['location_id']}"))
            elif order["location_company_id"] != order["company_id"]:
                issues.append(AuditIssue("Orders", f"Order ID {order['id']}: location belongs to another company"))
        if order["contact_id"] is not None:
            if order["contact_company_id"] is None:
                issues.append(AuditIssue("Orders", f"Order ID {order['id']}: missing contact {order['contact_id']}"))
            elif order["contact_company_id"] != order["company_id"]:
                issues.append(AuditIssue("Orders", f"Order ID {order['id']}: contact belongs to another company"))
        if order["opportunity_id"] is not None:
            if order["opportunity_company_id"] is None:
                issues.append(AuditIssue("Orders", f"Order ID {order['id']}: missing opportunity {order['opportunity_id']}"))
            elif order["opportunity_company_id"] != order["company_id"]:
                issues.append(AuditIssue("Orders", f"Order ID {order['id']}: opportunity belongs to another company"))

    item_counts = session.execute(
        text(
            "SELECT s.id, COUNT(si.id) AS item_count "
            "FROM sales s LEFT JOIN sale_items si ON si.sale_id = s.id "
            "GROUP BY s.id HAVING COUNT(si.id) = 0"
        )
    ).mappings()
    for order in item_counts:
        issues.append(AuditIssue("Orders", f"Order ID {order['id']}: no order items"))

    item_rows = session.execute(
        text(
            "SELECT si.id, si.sale_id, si.product_id, si.quantity, si.incremental_mrr, si.monthly_revenue, "
            "s.status AS order_status, p.id AS product_exists, p.active AS product_active "
            "FROM sale_items si "
            "LEFT JOIN sales s ON s.id = si.sale_id "
            "LEFT JOIN products p ON p.id = si.product_id "
            "ORDER BY si.id"
        )
    ).mappings()
    for item in item_rows:
        if item["product_id"] is None or item["product_exists"] is None:
            issues.append(AuditIssue("Orders", f"SaleItem ID {item['id']}: missing product"))
        if item["quantity"] is not None and item["quantity"] <= 0:
            issues.append(AuditIssue("Orders", f"SaleItem ID {item['id']}: quantity must be greater than zero"))
        mrr_value = item["incremental_mrr"] if item["incremental_mrr"] is not None else item["monthly_revenue"]
        if mrr_value is not None and mrr_value < 0:
            issues.append(AuditIssue("Orders", f"SaleItem ID {item['id']}: negative incremental MRR"))
        if item["product_active"] == 0 and item["order_status"] in {"DRAFT", "SUBMITTED", "SCHEDULED"}:
            issues.append(AuditIssue("Orders", f"SaleItem ID {item['id']}: inactive product on open order"))

    duplicates = session.execute(
        text(
            "SELECT sale_id, product_id, COUNT(*) AS row_count "
            "FROM sale_items WHERE product_id IS NOT NULL "
            "GROUP BY sale_id, product_id HAVING COUNT(*) > 1"
        )
    ).mappings()
    for duplicate in duplicates:
        issues.append(
            AuditIssue(
                "Orders",
                f"Order ID {duplicate['sale_id']}: duplicate product rows for product {duplicate['product_id']}",
            )
        )
    return issues


def run_audit() -> list[AuditIssue]:
    with SessionLocal() as session:
        return [
            *audit_contacts(session),
            *audit_locations(session),
            *audit_companies(session),
            *audit_referral_partners(session),
            *audit_opportunities(session),
            *audit_orders(session),
        ]


def main() -> int:
    if "--fix" in sys.argv:
        print("Data quality audit")
        print("--fix is not implemented yet. No data was changed.")
        return 2
    issues = run_audit()
    print("Data quality audit")
    grouped = {"Contacts": [], "Locations": [], "Companies": [], "Referral Partners": [], "Opportunities": [], "Orders": []}
    for issue in issues:
        grouped.setdefault(issue.category, []).append(issue.message)
    for category, messages in grouped.items():
        print(f"\n{category}:")
        if not messages:
            print("- No issues found.")
        else:
            for message in messages:
                print(f"- {message}")
    print(f"\n{len(issues)} issues found.")
    print("No data was changed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
