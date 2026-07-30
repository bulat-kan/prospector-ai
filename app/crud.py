from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.enums import ContactRole, LocationType, SpectrumRelationship, TerritoryStatus
from app.models import Company, Contact, Location, ReferralPartner
from app.validation import (
    LEAD_SOURCE_AE_FOUND,
    LEAD_SOURCE_REFERRAL,
    clean_optional_text,
    validate_company_name,
    validate_contact_identity,
    validate_lead_source,
    validate_location_fields,
    validate_referral_partner_identity,
    validate_source_metadata,
)


class CrudError(Exception):
    """Base error for reusable database operations."""


class ValidationError(CrudError):
    """Raised when input validation fails."""


class RecordNotFoundError(CrudError):
    """Raised when a requested record does not exist."""


class DuplicateRecordError(CrudError):
    """Raised when an operation would create a duplicate record."""


@dataclass(frozen=True)
class CompanyDTO:
    id: int
    name: str
    website: Optional[str]
    main_phone: Optional[str]
    industry: Optional[str]
    lead_source: Optional[str]
    lead_source_legacy: Optional[str]
    referral_partner_id: Optional[int]
    referral_partner_name: Optional[str]
    referral_partner_organization: Optional[str]
    referral_partner_registered: bool
    referred_at: Optional[datetime]
    is_active: bool
    status: Optional[str]
    notes: Optional[str]
    source_system: Optional[str]
    external_id: Optional[str]
    location_count: int = 0
    contact_count: int = 0
    opportunity_count: int = 0


@dataclass(frozen=True)
class LocationDTO:
    id: int
    company_id: int
    location_name: Optional[str]
    address_line_1: str
    address_line_2: Optional[str]
    city: str
    state: str
    postal_code: str
    location_type: LocationType
    territory_status: TerritoryStatus
    spectrum_relationship: SpectrumRelationship
    is_active: bool
    inactive_reason: Optional[str]
    inactive_at: Optional[datetime]
    current_provider_notes: Optional[str]
    source_system: Optional[str]
    external_id: Optional[str]


@dataclass(frozen=True)
class ContactDTO:
    id: int
    company_id: int
    location_id: Optional[int]
    first_name: Optional[str]
    last_name: Optional[str]
    job_title: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    decision_role: ContactRole
    is_primary_contact: bool
    is_active: bool
    inactive_reason: Optional[str]
    inactive_at: Optional[datetime]
    notes: Optional[str]
    source_system: Optional[str]
    external_id: Optional[str]


@dataclass(frozen=True)
class ReferralPartnerDTO:
    id: int
    first_name: Optional[str]
    last_name: Optional[str]
    organization: Optional[str]
    role_or_type: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    is_registered_spectrum_partner: bool
    spectrum_partner_reference: Optional[str]
    is_active: bool
    notes: Optional[str]
    source_system: Optional[str]
    external_id: Optional[str]

    @property
    def display_name(self) -> str:
        person = " ".join(value for value in (self.first_name, self.last_name) if value).strip()
        if person and self.organization:
            return f"{person} ({self.organization})"
        return person or self.organization or self.email or self.phone or f"Referral partner {self.id}"


def _partner_display_name(partner: Optional[ReferralPartner]) -> Optional[str]:
    if partner is None:
        return None
    person = " ".join(value for value in (partner.first_name, partner.last_name) if value).strip()
    if person and partner.organization:
        return f"{person} ({partner.organization})"
    return person or partner.organization or partner.email or partner.phone


def _company_to_dto(company: Company, location_count: int = 0, contact_count: int = 0, opportunity_count: int = 0) -> CompanyDTO:
    return CompanyDTO(
        id=company.id,
        name=company.name,
        website=company.website,
        main_phone=company.main_phone,
        industry=company.industry,
        lead_source=company.lead_source,
        lead_source_legacy=company.lead_source_legacy,
        referral_partner_id=company.referral_partner_id,
        referral_partner_name=_partner_display_name(company.referral_partner),
        referral_partner_organization=company.referral_partner.organization if company.referral_partner else None,
        referral_partner_registered=bool(company.referral_partner.is_registered_spectrum_partner) if company.referral_partner else False,
        referred_at=company.referred_at,
        is_active=company.is_active,
        status=company.status,
        notes=company.notes,
        source_system=company.source_system,
        external_id=company.external_id,
        location_count=location_count,
        contact_count=contact_count,
        opportunity_count=opportunity_count,
    )


def _location_to_dto(location: Location) -> LocationDTO:
    return LocationDTO(
        id=location.id,
        company_id=location.company_id,
        location_name=location.location_name,
        address_line_1=location.address_line_1,
        address_line_2=location.address_line_2,
        city=location.city,
        state=location.state,
        postal_code=location.postal_code,
        location_type=location.location_type,
        territory_status=location.territory_status,
        spectrum_relationship=location.spectrum_relationship,
        is_active=location.is_active,
        inactive_reason=location.inactive_reason,
        inactive_at=location.inactive_at,
        current_provider_notes=location.current_provider_notes,
        source_system=location.source_system,
        external_id=location.external_id,
    )


def _contact_to_dto(contact: Contact) -> ContactDTO:
    return ContactDTO(
        id=contact.id,
        company_id=contact.company_id,
        location_id=contact.location_id,
        first_name=contact.first_name,
        last_name=contact.last_name,
        job_title=contact.job_title,
        phone=contact.phone,
        email=contact.email,
        decision_role=contact.decision_role,
        is_primary_contact=contact.is_primary_contact,
        is_active=contact.is_active,
        inactive_reason=contact.inactive_reason,
        inactive_at=contact.inactive_at,
        notes=contact.notes,
        source_system=contact.source_system,
        external_id=contact.external_id,
    )


def _referral_partner_to_dto(partner: ReferralPartner) -> ReferralPartnerDTO:
    return ReferralPartnerDTO(
        id=partner.id,
        first_name=partner.first_name,
        last_name=partner.last_name,
        organization=partner.organization,
        role_or_type=partner.role_or_type,
        phone=partner.phone,
        email=partner.email,
        is_registered_spectrum_partner=partner.is_registered_spectrum_partner,
        spectrum_partner_reference=partner.spectrum_partner_reference,
        is_active=partner.is_active,
        notes=partner.notes,
        source_system=partner.source_system,
        external_id=partner.external_id,
    )


def _raise_validation(error: ValueError) -> None:
    raise ValidationError(str(error)) from error


def _normalize_source(source_system: Optional[str], external_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    try:
        return validate_source_metadata(source_system, external_id)
    except ValueError as exc:
        _raise_validation(exc)
        raise AssertionError("unreachable")


def _ensure_company(session: Session, company_id: int) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise RecordNotFoundError(f"Company id={company_id} was not found.")
    return company


def _ensure_location(session: Session, location_id: int) -> Location:
    location = session.get(Location, location_id)
    if location is None:
        raise RecordNotFoundError(f"Location id={location_id} was not found.")
    return location


def _ensure_contact(session: Session, contact_id: int) -> Contact:
    contact = session.get(Contact, contact_id)
    if contact is None:
        raise RecordNotFoundError(f"Contact id={contact_id} was not found.")
    return contact


def _ensure_referral_partner(session: Session, referral_partner_id: int) -> ReferralPartner:
    partner = session.get(ReferralPartner, referral_partner_id)
    if partner is None:
        raise RecordNotFoundError(f"Referral partner id={referral_partner_id} was not found.")
    return partner


def _check_source_duplicate(
    session: Session,
    model: type[Company] | type[Location] | type[Contact] | type[ReferralPartner],
    source_system: Optional[str],
    external_id: Optional[str],
    current_id: Optional[int] = None,
) -> None:
    if source_system is None or external_id is None:
        return
    query = select(model).where(model.source_system == source_system, model.external_id == external_id)
    existing = session.scalar(query)
    if existing is not None and existing.id != current_id:
        raise DuplicateRecordError(f"{model.__name__} already exists for source_system={source_system!r}, external_id={external_id!r}.")


def _handle_db_error(session: Session, error: SQLAlchemyError) -> None:
    session.rollback()
    raise CrudError("Database operation failed.") from error


def _validate_company_referral(
    session: Session,
    lead_source: Optional[str],
    referral_partner_id: Optional[int],
) -> Optional[ReferralPartner]:
    if referral_partner_id is None:
        if lead_source == LEAD_SOURCE_REFERRAL:
            raise ValidationError("Referral companies require a referral partner.")
        return None
    partner = _ensure_referral_partner(session, referral_partner_id)
    if lead_source is not None and lead_source != LEAD_SOURCE_REFERRAL:
        raise ValidationError("A referral partner can only be assigned when lead source is Referral.")
    return partner


def create_company(
    session: Session,
    *,
    name: str,
    website: Optional[str] = None,
    main_phone: Optional[str] = None,
    industry: Optional[str] = None,
    lead_source: Optional[str] = None,
    notes: Optional[str] = None,
    source_system: Optional[str] = None,
    external_id: Optional[str] = None,
    last_imported_at: Optional[datetime] = None,
    referral_partner_id: Optional[int] = None,
    referred_at: Optional[datetime] = None,
) -> CompanyDTO:
    try:
        clean_name = validate_company_name(name)
        normalized_source, normalized_external_id = _normalize_source(source_system, external_id)
        normalized_lead_source = validate_lead_source(lead_source)
        partner = _validate_company_referral(session, normalized_lead_source, referral_partner_id)
        existing_name = session.scalar(select(Company).where(func.lower(Company.name) == clean_name.lower()))
        if existing_name is not None:
            raise DuplicateRecordError(f"Company named {clean_name!r} already exists.")
        _check_source_duplicate(session, Company, normalized_source, normalized_external_id)
        company = Company(
            name=clean_name,
            website=clean_optional_text(website),
            main_phone=clean_optional_text(main_phone),
            industry=clean_optional_text(industry),
            lead_source=normalized_lead_source,
            referral_partner_id=partner.id if partner else None,
            referred_at=referred_at if partner else None,
            notes=clean_optional_text(notes),
            source_system=normalized_source,
            external_id=normalized_external_id,
            last_imported_at=last_imported_at,
        )
        session.add(company)
        session.commit()
        session.refresh(company)
        return _company_to_dto(company)
    except ValueError as exc:
        session.rollback()
        _raise_validation(exc)
    except DuplicateRecordError:
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
    raise AssertionError("unreachable")


def list_companies(session: Session, search: Optional[str] = None, include_archived: bool = False) -> tuple[CompanyDTO, ...]:
    query = select(Company).options(selectinload(Company.referral_partner)).order_by(Company.name)
    if not include_archived:
        query = query.where(Company.is_active.is_(True))
    companies = session.scalars(query).all()
    if search:
        needle = search.strip().lower()
        companies = [company for company in companies if needle in company.name.lower()]
    return tuple(
        _company_to_dto(company, len(company.locations), len(company.contacts), len(company.opportunities))
        for company in companies
    )


def get_company(session: Session, company_id: int) -> CompanyDTO:
    company = session.scalar(
        select(Company)
        .options(
            selectinload(Company.locations),
            selectinload(Company.contacts),
            selectinload(Company.opportunities),
            selectinload(Company.referral_partner),
        )
        .where(Company.id == company_id)
    )
    if company is None:
        raise RecordNotFoundError(f"Company id={company_id} was not found.")
    return _company_to_dto(company, len(company.locations), len(company.contacts), len(company.opportunities))


def update_company(session: Session, company_id: int, **fields: object) -> CompanyDTO:
    try:
        company = _ensure_company(session, company_id)
        if "name" in fields:
            clean_name = validate_company_name(fields["name"])  # type: ignore[arg-type]
            duplicate = session.scalar(
                select(Company).where(func.lower(Company.name) == clean_name.lower(), Company.id != company_id)
            )
            if duplicate is not None:
                raise DuplicateRecordError(f"Company named {clean_name!r} already exists.")
            company.name = clean_name
        if "source_system" in fields or "external_id" in fields:
            source_system = fields.get("source_system", company.source_system)  # type: ignore[arg-type]
            external_id = fields.get("external_id", company.external_id)  # type: ignore[arg-type]
            normalized_source, normalized_external_id = _normalize_source(source_system, external_id)
            _check_source_duplicate(session, Company, normalized_source, normalized_external_id, company_id)
            company.source_system = normalized_source
            company.external_id = normalized_external_id
        if "lead_source" in fields or "referral_partner_id" in fields:
            next_lead_source = validate_lead_source(fields.get("lead_source", company.lead_source))  # type: ignore[arg-type]
            next_partner_id = fields.get("referral_partner_id", company.referral_partner_id)  # type: ignore[arg-type]
            partner = _validate_company_referral(session, next_lead_source, next_partner_id)  # type: ignore[arg-type]
            company.lead_source = next_lead_source
            company.referral_partner_id = partner.id if partner else None
            if partner and company.referred_at is None:
                company.referred_at = fields.get("referred_at") or datetime.now(UTC)  # type: ignore[assignment]
            if not partner:
                company.referred_at = None
        for attr in ("website", "main_phone", "industry", "status", "notes"):
            if attr in fields:
                setattr(company, attr, clean_optional_text(fields[attr]))  # type: ignore[arg-type]
        if "is_active" in fields:
            company.is_active = bool(fields["is_active"])
        session.commit()
        session.refresh(company)
        return get_company(session, company.id)
    except ValueError as exc:
        session.rollback()
        _raise_validation(exc)
    except (DuplicateRecordError, RecordNotFoundError):
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
    raise AssertionError("unreachable")


def archive_company(session: Session, company_id: int) -> CompanyDTO:
    return update_company(session, company_id, is_active=False)


def restore_company(session: Session, company_id: int) -> CompanyDTO:
    return update_company(session, company_id, is_active=True)


def assign_referral_partner(session: Session, company_id: int, referral_partner_id: int, referred_at: Optional[datetime] = None) -> CompanyDTO:
    _ensure_referral_partner(session, referral_partner_id)
    return update_company(
        session,
        company_id,
        lead_source=LEAD_SOURCE_REFERRAL,
        referral_partner_id=referral_partner_id,
        referred_at=referred_at or datetime.now(UTC),
    )


def remove_or_change_referral_partner(
    session: Session,
    company_id: int,
    *,
    new_referral_partner_id: Optional[int] = None,
    new_lead_source: Optional[str] = None,
    confirm_clear: bool = False,
) -> CompanyDTO:
    if new_referral_partner_id is not None:
        return assign_referral_partner(session, company_id, new_referral_partner_id)
    lead_source = validate_lead_source(new_lead_source)
    if lead_source != LEAD_SOURCE_AE_FOUND:
        raise ValidationError("Clearing a referral partner requires changing lead source to AE Found.")
    if not confirm_clear:
        raise ValidationError("Confirm clearing the referral partner before changing lead source.")
    return update_company(session, company_id, lead_source=LEAD_SOURCE_AE_FOUND, referral_partner_id=None)


def create_location(
    session: Session,
    *,
    company_id: int,
    address_line_1: str,
    city: str,
    state: str,
    postal_code: str,
    location_type: LocationType,
    location_name: Optional[str] = None,
    address_line_2: Optional[str] = None,
    territory_status: TerritoryStatus = TerritoryStatus.UNKNOWN,
    spectrum_relationship: SpectrumRelationship = SpectrumRelationship.UNKNOWN,
    current_provider_notes: Optional[str] = None,
    source_system: Optional[str] = None,
    external_id: Optional[str] = None,
    last_imported_at: Optional[datetime] = None,
) -> LocationDTO:
    try:
        validate_location_fields(company_id, city, state, postal_code)
        _ensure_company(session, company_id)
        normalized_source, normalized_external_id = _normalize_source(source_system, external_id)
        _check_source_duplicate(session, Location, normalized_source, normalized_external_id)
        location = Location(
            company_id=company_id,
            location_name=clean_optional_text(location_name),
            address_line_1=clean_optional_text(address_line_1) or "",
            address_line_2=clean_optional_text(address_line_2),
            city=clean_optional_text(city) or "",
            state=(clean_optional_text(state) or "").upper(),
            postal_code=clean_optional_text(postal_code) or "",
            location_type=location_type,
            territory_status=territory_status,
            spectrum_relationship=spectrum_relationship,
            current_provider_notes=clean_optional_text(current_provider_notes),
            source_system=normalized_source,
            external_id=normalized_external_id,
            last_imported_at=last_imported_at,
        )
        session.add(location)
        session.commit()
        session.refresh(location)
        return _location_to_dto(location)
    except ValueError as exc:
        session.rollback()
        _raise_validation(exc)
    except (DuplicateRecordError, RecordNotFoundError):
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
    raise AssertionError("unreachable")


def list_company_locations(session: Session, company_id: int, include_inactive: bool = False) -> tuple[LocationDTO, ...]:
    _ensure_company(session, company_id)
    query = select(Location).where(Location.company_id == company_id).order_by(Location.location_name, Location.id)
    if not include_inactive:
        query = query.where(Location.is_active.is_(True))
    locations = session.scalars(query).all()
    return tuple(_location_to_dto(location) for location in locations)


def get_location(session: Session, location_id: int) -> LocationDTO:
    return _location_to_dto(_ensure_location(session, location_id))


def update_location(session: Session, location_id: int, **fields: object) -> LocationDTO:
    try:
        location = _ensure_location(session, location_id)
        if "company_id" in fields:
            _ensure_company(session, fields["company_id"])  # type: ignore[arg-type]
            location.company_id = fields["company_id"]  # type: ignore[assignment]
        validate_location_fields(location.company_id, fields.get("city", location.city), fields.get("state", location.state), fields.get("postal_code", location.postal_code))  # type: ignore[arg-type]
        if "source_system" in fields or "external_id" in fields:
            normalized_source, normalized_external_id = _normalize_source(
                fields.get("source_system", location.source_system),  # type: ignore[arg-type]
                fields.get("external_id", location.external_id),  # type: ignore[arg-type]
            )
            _check_source_duplicate(session, Location, normalized_source, normalized_external_id, location_id)
            location.source_system = normalized_source
            location.external_id = normalized_external_id
        for attr in ("location_name", "address_line_1", "address_line_2", "city", "state", "postal_code", "current_provider_notes"):
            if attr in fields:
                value = clean_optional_text(fields[attr])  # type: ignore[arg-type]
                if attr in {"address_line_1", "city", "state", "postal_code"}:
                    setattr(location, attr, value or "")
                else:
                    setattr(location, attr, value)
        if "state" in fields and location.state:
            location.state = location.state.upper()
        for attr in ("location_type", "territory_status", "spectrum_relationship"):
            if attr in fields:
                setattr(location, attr, fields[attr])
        if "is_active" in fields:
            location.is_active = bool(fields["is_active"])
        if "inactive_reason" in fields:
            location.inactive_reason = clean_optional_text(fields["inactive_reason"])  # type: ignore[arg-type]
        if "inactive_at" in fields:
            location.inactive_at = fields["inactive_at"]  # type: ignore[assignment]
        session.commit()
        session.refresh(location)
        return _location_to_dto(location)
    except ValueError as exc:
        session.rollback()
        _raise_validation(exc)
    except (DuplicateRecordError, RecordNotFoundError):
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
    raise AssertionError("unreachable")


def deactivate_location(session: Session, location_id: int, reason: str) -> LocationDTO:
    reason_text = clean_optional_text(reason)
    if reason_text is None:
        raise ValidationError("Inactive reason is required.")
    return update_location(session, location_id, is_active=False, inactive_reason=reason_text, inactive_at=datetime.now(UTC))


def restore_location(session: Session, location_id: int) -> LocationDTO:
    return update_location(session, location_id, is_active=True, inactive_reason=None, inactive_at=None)


def create_contact(
    session: Session,
    *,
    company_id: int,
    location_id: Optional[int] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    job_title: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    decision_role: ContactRole = ContactRole.UNKNOWN,
    is_primary_contact: bool = False,
    notes: Optional[str] = None,
    source_system: Optional[str] = None,
    external_id: Optional[str] = None,
    last_imported_at: Optional[datetime] = None,
) -> ContactDTO:
    try:
        _ensure_company(session, company_id)
        if location_id is not None:
            location = _ensure_location(session, location_id)
            if location.company_id != company_id:
                raise ValidationError("Contact location must belong to the same company.")
        validate_contact_identity(first_name, last_name, email, phone)
        normalized_source, normalized_external_id = _normalize_source(source_system, external_id)
        _check_source_duplicate(session, Contact, normalized_source, normalized_external_id)
        contact = Contact(
            company_id=company_id,
            location_id=location_id,
            first_name=clean_optional_text(first_name),
            last_name=clean_optional_text(last_name),
            job_title=clean_optional_text(job_title),
            phone=clean_optional_text(phone),
            email=clean_optional_text(email),
            decision_role=decision_role,
            is_primary_contact=is_primary_contact,
            notes=clean_optional_text(notes),
            source_system=normalized_source,
            external_id=normalized_external_id,
            last_imported_at=last_imported_at,
        )
        session.add(contact)
        session.commit()
        session.refresh(contact)
        return _contact_to_dto(contact)
    except ValueError as exc:
        session.rollback()
        _raise_validation(exc)
    except (DuplicateRecordError, RecordNotFoundError, ValidationError):
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
    raise AssertionError("unreachable")


def list_company_contacts(session: Session, company_id: int, include_inactive: bool = False) -> tuple[ContactDTO, ...]:
    _ensure_company(session, company_id)
    query = select(Contact).where(Contact.company_id == company_id).order_by(Contact.last_name, Contact.first_name, Contact.id)
    if not include_inactive:
        query = query.where(Contact.is_active.is_(True))
    contacts = session.scalars(query).all()
    return tuple(_contact_to_dto(contact) for contact in contacts)


def get_contact(session: Session, contact_id: int) -> ContactDTO:
    return _contact_to_dto(_ensure_contact(session, contact_id))


def update_contact(session: Session, contact_id: int, **fields: object) -> ContactDTO:
    try:
        contact = _ensure_contact(session, contact_id)
        if "company_id" in fields:
            _ensure_company(session, fields["company_id"])  # type: ignore[arg-type]
            contact.company_id = fields["company_id"]  # type: ignore[assignment]
        if "location_id" in fields:
            location_id = fields["location_id"]
            if location_id is not None:
                location = _ensure_location(session, location_id)  # type: ignore[arg-type]
                if location.company_id != contact.company_id:
                    raise ValidationError("Contact location must belong to the same company.")
            contact.location_id = location_id  # type: ignore[assignment]
        next_values = {
            "first_name": fields.get("first_name", contact.first_name),
            "last_name": fields.get("last_name", contact.last_name),
            "email": fields.get("email", contact.email),
            "phone": fields.get("phone", contact.phone),
        }
        validate_contact_identity(**next_values)  # type: ignore[arg-type]
        if "source_system" in fields or "external_id" in fields:
            normalized_source, normalized_external_id = _normalize_source(
                fields.get("source_system", contact.source_system),  # type: ignore[arg-type]
                fields.get("external_id", contact.external_id),  # type: ignore[arg-type]
            )
            _check_source_duplicate(session, Contact, normalized_source, normalized_external_id, contact_id)
            contact.source_system = normalized_source
            contact.external_id = normalized_external_id
        for attr in ("first_name", "last_name", "job_title", "phone", "email", "notes"):
            if attr in fields:
                setattr(contact, attr, clean_optional_text(fields[attr]))  # type: ignore[arg-type]
        if "decision_role" in fields:
            contact.decision_role = fields["decision_role"]  # type: ignore[assignment]
        if "is_primary_contact" in fields:
            contact.is_primary_contact = bool(fields["is_primary_contact"])
        if "is_active" in fields:
            contact.is_active = bool(fields["is_active"])
        if "inactive_reason" in fields:
            contact.inactive_reason = clean_optional_text(fields["inactive_reason"])  # type: ignore[arg-type]
        if "inactive_at" in fields:
            contact.inactive_at = fields["inactive_at"]  # type: ignore[assignment]
        session.commit()
        session.refresh(contact)
        return _contact_to_dto(contact)
    except ValueError as exc:
        session.rollback()
        _raise_validation(exc)
    except (DuplicateRecordError, RecordNotFoundError, ValidationError):
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
    raise AssertionError("unreachable")


def deactivate_contact(session: Session, contact_id: int, reason: Optional[str] = None) -> ContactDTO:
    return update_contact(session, contact_id, is_active=False, inactive_reason=reason, inactive_at=datetime.now(UTC))


def restore_contact(session: Session, contact_id: int) -> ContactDTO:
    return update_contact(session, contact_id, is_active=True, inactive_reason=None, inactive_at=None)


def create_referral_partner(
    session: Session,
    *,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    organization: Optional[str] = None,
    role_or_type: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    is_registered_spectrum_partner: bool = False,
    spectrum_partner_reference: Optional[str] = None,
    notes: Optional[str] = None,
    source_system: Optional[str] = None,
    external_id: Optional[str] = None,
    last_imported_at: Optional[datetime] = None,
) -> ReferralPartnerDTO:
    try:
        validate_referral_partner_identity(first_name, last_name, organization, phone, email)
        normalized_source, normalized_external_id = _normalize_source(source_system, external_id)
        _check_source_duplicate(session, ReferralPartner, normalized_source, normalized_external_id)
        partner = ReferralPartner(
            first_name=clean_optional_text(first_name),
            last_name=clean_optional_text(last_name),
            organization=clean_optional_text(organization),
            role_or_type=clean_optional_text(role_or_type),
            phone=clean_optional_text(phone),
            email=clean_optional_text(email),
            is_registered_spectrum_partner=is_registered_spectrum_partner,
            spectrum_partner_reference=clean_optional_text(spectrum_partner_reference),
            notes=clean_optional_text(notes),
            source_system=normalized_source,
            external_id=normalized_external_id,
            last_imported_at=last_imported_at,
        )
        session.add(partner)
        session.commit()
        session.refresh(partner)
        return _referral_partner_to_dto(partner)
    except ValueError as exc:
        session.rollback()
        _raise_validation(exc)
    except DuplicateRecordError:
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
    raise AssertionError("unreachable")


def list_referral_partners(session: Session, include_inactive: bool = False) -> tuple[ReferralPartnerDTO, ...]:
    query = select(ReferralPartner).order_by(ReferralPartner.organization, ReferralPartner.last_name, ReferralPartner.first_name, ReferralPartner.id)
    if not include_inactive:
        query = query.where(ReferralPartner.is_active.is_(True))
    return tuple(_referral_partner_to_dto(partner) for partner in session.scalars(query).all())


def get_referral_partner(session: Session, referral_partner_id: int) -> ReferralPartnerDTO:
    return _referral_partner_to_dto(_ensure_referral_partner(session, referral_partner_id))


def update_referral_partner(session: Session, referral_partner_id: int, **fields: object) -> ReferralPartnerDTO:
    try:
        partner = _ensure_referral_partner(session, referral_partner_id)
        next_values = {
            "first_name": fields.get("first_name", partner.first_name),
            "last_name": fields.get("last_name", partner.last_name),
            "organization": fields.get("organization", partner.organization),
            "phone": fields.get("phone", partner.phone),
            "email": fields.get("email", partner.email),
        }
        validate_referral_partner_identity(**next_values)  # type: ignore[arg-type]
        if "source_system" in fields or "external_id" in fields:
            normalized_source, normalized_external_id = _normalize_source(
                fields.get("source_system", partner.source_system),  # type: ignore[arg-type]
                fields.get("external_id", partner.external_id),  # type: ignore[arg-type]
            )
            _check_source_duplicate(session, ReferralPartner, normalized_source, normalized_external_id, referral_partner_id)
            partner.source_system = normalized_source
            partner.external_id = normalized_external_id
        for attr in ("first_name", "last_name", "organization", "role_or_type", "phone", "email", "spectrum_partner_reference", "notes"):
            if attr in fields:
                setattr(partner, attr, clean_optional_text(fields[attr]))  # type: ignore[arg-type]
        if "is_registered_spectrum_partner" in fields:
            partner.is_registered_spectrum_partner = bool(fields["is_registered_spectrum_partner"])
        if "is_active" in fields:
            partner.is_active = bool(fields["is_active"])
        session.commit()
        session.refresh(partner)
        return _referral_partner_to_dto(partner)
    except ValueError as exc:
        session.rollback()
        _raise_validation(exc)
    except (DuplicateRecordError, RecordNotFoundError):
        session.rollback()
        raise
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
    raise AssertionError("unreachable")


def deactivate_referral_partner(session: Session, referral_partner_id: int) -> ReferralPartnerDTO:
    return update_referral_partner(session, referral_partner_id, is_active=False)


def restore_referral_partner(session: Session, referral_partner_id: int) -> ReferralPartnerDTO:
    return update_referral_partner(session, referral_partner_id, is_active=True)
