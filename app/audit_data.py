import sys
from dataclasses import dataclass

from sqlalchemy import select, text

from app.database import SessionLocal
from app.models import Location
from app.validation import (
    normalize_city,
    normalize_company_phone,
    normalize_contact_phone,
    normalize_email,
    normalize_website,
    normalize_zip_code,
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
        except ValueError:
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


def run_audit() -> list[AuditIssue]:
    with SessionLocal() as session:
        return [*audit_contacts(session), *audit_locations(session), *audit_companies(session)]


def main() -> int:
    if "--fix" in sys.argv:
        print("Data quality audit")
        print("--fix is not implemented yet. No data was changed.")
        return 2
    issues = run_audit()
    print("Data quality audit")
    grouped = {"Contacts": [], "Locations": [], "Companies": []}
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
