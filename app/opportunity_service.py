from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import case, exists, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.constants import (
    CLOSED_OPPORTUNITY_STAGES,
    LEGACY_OPPORTUNITY_STAGE_MAP,
    OPEN_OPPORTUNITY_STAGES,
    OPPORTUNITY_STAGE_CLOSED_LOST,
    OPPORTUNITY_STAGE_LABELS,
    OPPORTUNITY_STAGES,
)
from app.crud import RecordNotFoundError
from app.enums import OpportunityStage
from app.models import Company, Contact, Location, Opportunity, OpportunityProduct, Product
from app.validation import clean_optional_text, require_text


MONEY_QUANT = Decimal("0.01")


class OpportunityError(Exception):
    """Base error for opportunity service operations."""


class OpportunityValidationError(OpportunityError):
    """Raised when opportunity input violates business rules."""


class DuplicateOpportunityProductError(OpportunityValidationError):
    """Raised when an opportunity would contain duplicate product rows."""


@dataclass(frozen=True)
class OpportunityProductInput:
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    estimated_quantity: int = 0
    estimated_incremental_mrr: Decimal = Decimal("0.00")
    interest_level: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class OpportunityProductDTO:
    id: int
    opportunity_id: int
    product_id: Optional[int]
    product_code: str
    product_name: str
    estimated_quantity: int
    estimated_incremental_mrr: Decimal
    interest_level: Optional[str]
    notes: Optional[str]


@dataclass(frozen=True)
class CreatedOpportunityResult:
    opportunity_id: int
    opportunity_name: str
    company_id: int
    company_name: str


@dataclass(frozen=True)
class OpportunitySummary:
    id: int
    company_id: int
    company_name: str
    location_id: Optional[int]
    location_name: Optional[str]
    primary_contact_id: Optional[int]
    primary_contact_name: Optional[str]
    name: str
    stage: OpportunityStage
    stage_display: str
    product_names: tuple[str, ...]
    estimated_total_quantity: int
    estimated_mrr: Optional[Decimal]
    internet_probability: int
    priority_score: int
    next_action: Optional[str]
    next_action_date: Optional[date]
    expected_close_date: Optional[date]
    is_overdue: bool
    is_active: bool


@dataclass(frozen=True)
class OpportunityDetail:
    summary: OpportunitySummary
    notes: Optional[str]
    lost_reason: Optional[str]
    revenue_potential_score: int
    cross_sell_score: int
    score_reason: Optional[str]
    products: tuple[OpportunityProductDTO, ...]
    created_at: datetime
    updated_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def money(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def normalize_opportunity_stage(stage: OpportunityStage | str | None) -> OpportunityStage:
    if stage is None:
        return OpportunityStage.NEW
    raw = stage.value if isinstance(stage, OpportunityStage) else str(stage)
    normalized = LEGACY_OPPORTUNITY_STAGE_MAP.get(raw, raw)
    if normalized not in OPPORTUNITY_STAGES:
        raise OpportunityValidationError(f"Unsupported opportunity stage: {raw}.")
    return OpportunityStage(normalized)


def stage_display(stage: OpportunityStage | str) -> str:
    normalized = normalize_opportunity_stage(stage)
    return OPPORTUNITY_STAGE_LABELS[normalized.value]


def is_open_stage(stage: OpportunityStage | str) -> bool:
    return normalize_opportunity_stage(stage).value in OPEN_OPPORTUNITY_STAGES


def is_closed_stage(stage: OpportunityStage | str) -> bool:
    return normalize_opportunity_stage(stage).value in CLOSED_OPPORTUNITY_STAGES


def validate_score(value: int, field_name: str) -> int:
    if value < 0 or value > 100:
        raise OpportunityValidationError(f"{field_name} must be between 0 and 100.")
    return value


def validate_nonnegative_quantity(value: int) -> int:
    if value < 0:
        raise OpportunityValidationError("Estimated quantity must be zero or greater.")
    return value


def validate_nonnegative_money(value: Decimal | int | str | None) -> Decimal:
    amount = money(value)
    if amount < Decimal("0.00"):
        raise OpportunityValidationError("Estimated incremental MRR must be zero or greater.")
    return amount


def validate_follow_up_rules(
    *,
    stage: OpportunityStage,
    next_action: Optional[str],
    next_action_date: Optional[date],
    lost_reason: Optional[str],
) -> None:
    if is_open_stage(stage):
        if clean_optional_text(next_action) is None:
            raise OpportunityValidationError("Open opportunities require a next action.")
        if next_action_date is None:
            raise OpportunityValidationError("Open opportunities require a next action date.")
    if stage.value == OPPORTUNITY_STAGE_CLOSED_LOST and clean_optional_text(lost_reason) is None:
        raise OpportunityValidationError("Closed Lost opportunities require a lost reason.")


def _handle_db_error(session: Session, error: SQLAlchemyError) -> None:
    session.rollback()
    raise OpportunityError("Opportunity database operation failed.") from error


def _ensure_company(session: Session, company_id: int, *, require_active: bool = False) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise RecordNotFoundError(f"Company id={company_id} was not found.")
    if require_active and not company.is_active:
        raise OpportunityValidationError(f"Company id={company_id} is inactive.")
    return company


def _ensure_location(
    session: Session,
    location_id: Optional[int],
    *,
    company_id: int,
    require_active: bool = False,
) -> Optional[Location]:
    if location_id is None:
        return None
    location = session.get(Location, location_id)
    if location is None:
        raise RecordNotFoundError(f"Location id={location_id} was not found.")
    if location.company_id != company_id:
        raise OpportunityValidationError(f"Location id={location_id} does not belong to company id={company_id}.")
    if require_active and not location.is_active:
        raise OpportunityValidationError(f"Location id={location_id} is inactive.")
    return location


def _ensure_contact(
    session: Session,
    contact_id: Optional[int],
    *,
    company_id: int,
    require_active: bool = False,
) -> Optional[Contact]:
    if contact_id is None:
        return None
    contact = session.get(Contact, contact_id)
    if contact is None:
        raise RecordNotFoundError(f"Contact id={contact_id} was not found.")
    if contact.company_id != company_id:
        raise OpportunityValidationError(f"Contact id={contact_id} does not belong to company id={company_id}.")
    if require_active and not contact.is_active:
        raise OpportunityValidationError(f"Contact id={contact_id} is inactive.")
    return contact


def _ensure_opportunity(session: Session, opportunity_id: int) -> Opportunity:
    opportunity = session.scalar(
        select(Opportunity)
        .options(
            selectinload(Opportunity.company),
            selectinload(Opportunity.location),
            selectinload(Opportunity.primary_contact),
            selectinload(Opportunity.products).selectinload(OpportunityProduct.product),
        )
        .where(Opportunity.id == opportunity_id)
        .execution_options(populate_existing=True)
    )
    if opportunity is None:
        raise RecordNotFoundError(f"Opportunity id={opportunity_id} was not found.")
    return opportunity


def _ensure_product(session: Session, *, product_id: Optional[int], product_code: Optional[str]) -> Product:
    product: Optional[Product] = None
    if product_id is not None:
        product = session.get(Product, product_id)
    elif product_code is not None:
        product = session.scalar(select(Product).where(Product.code == product_code))
    if product is None:
        identity = f"id={product_id}" if product_id is not None else f"code={product_code!r}"
        raise RecordNotFoundError(f"Product {identity} was not found.")
    if not product.active:
        raise OpportunityValidationError(f"Product {product.code} is inactive.")
    return product


def _build_product_row(session: Session, opportunity: Opportunity, input_row: OpportunityProductInput) -> OpportunityProduct:
    product = _ensure_product(session, product_id=input_row.product_id, product_code=input_row.product_code)
    return OpportunityProduct(
        opportunity=opportunity,
        product=product,
        product_code=product.code,
        estimated_quantity=validate_nonnegative_quantity(input_row.estimated_quantity),
        estimated_incremental_mrr=validate_nonnegative_money(input_row.estimated_incremental_mrr),
        interest_level=clean_optional_text(input_row.interest_level),
        notes=clean_optional_text(input_row.notes),
    )


def _validate_no_duplicate_product_codes(product_rows: list[OpportunityProduct]) -> None:
    seen: set[str] = set()
    for row in product_rows:
        if row.product_code in seen:
            raise DuplicateOpportunityProductError(f"Opportunity already has product {row.product_code}.")
        seen.add(row.product_code)


def _validate_opportunity_fields(
    *,
    name: str,
    stage: OpportunityStage,
    next_action: Optional[str],
    next_action_date: Optional[date],
    lost_reason: Optional[str],
    internet_probability: int,
    revenue_potential_score: int,
    cross_sell_score: int,
    priority_score: int,
    estimated_mrr: Decimal | int | str | None,
) -> tuple[str, Decimal | None]:
    try:
        cleaned_name = require_text(name, "Opportunity name")
    except ValueError as exc:
        raise OpportunityValidationError(str(exc)) from exc
    validate_score(internet_probability, "Internet probability")
    validate_score(revenue_potential_score, "Revenue potential score")
    validate_score(cross_sell_score, "Cross-sell score")
    validate_score(priority_score, "Priority score")
    validate_follow_up_rules(
        stage=stage,
        next_action=next_action,
        next_action_date=next_action_date,
        lost_reason=lost_reason,
    )
    estimated_mrr_value = None if estimated_mrr is None else validate_nonnegative_money(estimated_mrr)
    return cleaned_name, estimated_mrr_value


def create_opportunity(
    session: Session,
    *,
    company_id: int,
    name: str,
    stage: OpportunityStage | str = OpportunityStage.NEW,
    location_id: Optional[int] = None,
    primary_contact_id: Optional[int] = None,
    expected_close_date: Optional[date] = None,
    next_action: Optional[str] = None,
    next_action_date: Optional[date] = None,
    lost_reason: Optional[str] = None,
    notes: Optional[str] = None,
    score_reason: Optional[str] = None,
    ai_summary: Optional[str] = None,
    internet_probability: int = 0,
    revenue_potential_score: int = 0,
    cross_sell_score: int = 0,
    priority_score: int = 0,
    estimated_mrr: Decimal | int | str | None = None,
) -> Opportunity:
    try:
        normalized_stage = normalize_opportunity_stage(stage)
        company = _ensure_company(session, company_id, require_active=True)
        location = _ensure_location(session, location_id, company_id=company.id, require_active=True)
        contact = _ensure_contact(session, primary_contact_id, company_id=company.id, require_active=True)
        cleaned_name, estimated_mrr_value = _validate_opportunity_fields(
            name=name,
            stage=normalized_stage,
            next_action=next_action,
            next_action_date=next_action_date,
            lost_reason=lost_reason,
            internet_probability=internet_probability,
            revenue_potential_score=revenue_potential_score,
            cross_sell_score=cross_sell_score,
            priority_score=priority_score,
            estimated_mrr=estimated_mrr,
        )
        opportunity = Opportunity(
            company=company,
            location=location,
            primary_contact=contact,
            name=cleaned_name,
            stage=normalized_stage,
            expected_close_date=expected_close_date,
            next_action=clean_optional_text(next_action),
            next_action_date=next_action_date,
            lost_reason=clean_optional_text(lost_reason),
            notes=clean_optional_text(notes),
            score_reason=clean_optional_text(score_reason),
            ai_summary=clean_optional_text(ai_summary),
            internet_probability=internet_probability,
            revenue_potential_score=revenue_potential_score,
            cross_sell_score=cross_sell_score,
            priority_score=priority_score,
            estimated_mrr=estimated_mrr_value,
        )
        session.add(opportunity)
        session.commit()
        session.refresh(opportunity)
        return opportunity
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")
    except Exception:
        session.rollback()
        raise


def create_opportunity_with_products(
    session: Session,
    *,
    products: list[OpportunityProductInput],
    **opportunity_kwargs,
) -> Opportunity:
    try:
        normalized_stage = normalize_opportunity_stage(opportunity_kwargs.get("stage", OpportunityStage.NEW))
        company = _ensure_company(session, opportunity_kwargs["company_id"], require_active=True)
        location = _ensure_location(session, opportunity_kwargs.get("location_id"), company_id=company.id, require_active=True)
        contact = _ensure_contact(session, opportunity_kwargs.get("primary_contact_id"), company_id=company.id, require_active=True)
        cleaned_name, estimated_mrr_value = _validate_opportunity_fields(
            name=opportunity_kwargs["name"],
            stage=normalized_stage,
            next_action=opportunity_kwargs.get("next_action"),
            next_action_date=opportunity_kwargs.get("next_action_date"),
            lost_reason=opportunity_kwargs.get("lost_reason"),
            internet_probability=opportunity_kwargs.get("internet_probability", 0),
            revenue_potential_score=opportunity_kwargs.get("revenue_potential_score", 0),
            cross_sell_score=opportunity_kwargs.get("cross_sell_score", 0),
            priority_score=opportunity_kwargs.get("priority_score", 0),
            estimated_mrr=opportunity_kwargs.get("estimated_mrr"),
        )
        opportunity = Opportunity(
            company=company,
            location=location,
            primary_contact=contact,
            name=cleaned_name,
            stage=normalized_stage,
            expected_close_date=opportunity_kwargs.get("expected_close_date"),
            next_action=clean_optional_text(opportunity_kwargs.get("next_action")),
            next_action_date=opportunity_kwargs.get("next_action_date"),
            lost_reason=clean_optional_text(opportunity_kwargs.get("lost_reason")),
            notes=clean_optional_text(opportunity_kwargs.get("notes")),
            score_reason=clean_optional_text(opportunity_kwargs.get("score_reason")),
            ai_summary=clean_optional_text(opportunity_kwargs.get("ai_summary")),
            internet_probability=opportunity_kwargs.get("internet_probability", 0),
            revenue_potential_score=opportunity_kwargs.get("revenue_potential_score", 0),
            cross_sell_score=opportunity_kwargs.get("cross_sell_score", 0),
            priority_score=opportunity_kwargs.get("priority_score", 0),
            estimated_mrr=estimated_mrr_value,
        )
        product_rows = [_build_product_row(session, opportunity, row) for row in products]
        _validate_no_duplicate_product_codes(product_rows)
        opportunity.products = product_rows
        session.add(opportunity)
        session.commit()
        return get_opportunity(session, opportunity.id)
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")
    except Exception:
        session.rollback()
        raise


def opportunity_to_created_result(opportunity: Opportunity) -> CreatedOpportunityResult:
    return CreatedOpportunityResult(
        opportunity_id=opportunity.id,
        opportunity_name=opportunity.name,
        company_id=opportunity.company_id,
        company_name=opportunity.company.name,
    )


def create_opportunity_result_with_products(
    session: Session,
    *,
    products: list[OpportunityProductInput],
    **opportunity_kwargs,
) -> CreatedOpportunityResult:
    opportunity = create_opportunity_with_products(session, products=products, **opportunity_kwargs)
    return opportunity_to_created_result(opportunity)


def get_opportunity(session: Session, opportunity_id: int) -> Opportunity:
    return _ensure_opportunity(session, opportunity_id)


def update_opportunity(session: Session, opportunity_id: int, **changes) -> Opportunity:
    try:
        opportunity = _ensure_opportunity(session, opportunity_id)
        company_id = changes.get("company_id", opportunity.company_id)
        _ensure_company(session, company_id)
        if "location_id" in changes:
            _ensure_location(session, changes["location_id"], company_id=company_id, require_active=True)
        if "primary_contact_id" in changes:
            _ensure_contact(session, changes["primary_contact_id"], company_id=company_id, require_active=True)
        stage = normalize_opportunity_stage(changes.get("stage", opportunity.stage))
        name = changes.get("name", opportunity.name)
        estimated_mrr = changes.get("estimated_mrr", opportunity.estimated_mrr)
        cleaned_name, estimated_mrr_value = _validate_opportunity_fields(
            name=name,
            stage=stage,
            next_action=changes.get("next_action", opportunity.next_action),
            next_action_date=changes.get("next_action_date", opportunity.next_action_date),
            lost_reason=changes.get("lost_reason", opportunity.lost_reason),
            internet_probability=changes.get("internet_probability", opportunity.internet_probability),
            revenue_potential_score=changes.get("revenue_potential_score", opportunity.revenue_potential_score),
            cross_sell_score=changes.get("cross_sell_score", opportunity.cross_sell_score),
            priority_score=changes.get("priority_score", opportunity.priority_score),
            estimated_mrr=estimated_mrr,
        )
        opportunity.name = cleaned_name
        opportunity.stage = stage
        opportunity.estimated_mrr = estimated_mrr_value
        for field_name in (
            "company_id",
            "location_id",
            "primary_contact_id",
            "expected_close_date",
            "next_action_date",
            "internet_probability",
            "revenue_potential_score",
            "cross_sell_score",
            "priority_score",
        ):
            if field_name in changes:
                setattr(opportunity, field_name, changes[field_name])
        for field_name in ("next_action", "lost_reason", "notes", "score_reason", "ai_summary"):
            if field_name in changes:
                setattr(opportunity, field_name, clean_optional_text(changes[field_name]))
        session.commit()
        return get_opportunity(session, opportunity.id)
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")
    except Exception:
        session.rollback()
        raise


def archive_opportunity(session: Session, opportunity_id: int) -> Opportunity:
    try:
        opportunity = _ensure_opportunity(session, opportunity_id)
        opportunity.is_active = False
        opportunity.archived_at = utc_now()
        session.commit()
        return get_opportunity(session, opportunity.id)
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")


def restore_opportunity(session: Session, opportunity_id: int) -> Opportunity:
    try:
        opportunity = _ensure_opportunity(session, opportunity_id)
        opportunity.is_active = True
        opportunity.archived_at = None
        session.commit()
        return get_opportunity(session, opportunity.id)
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")


def add_opportunity_product(session: Session, opportunity_id: int, product_input: OpportunityProductInput) -> OpportunityProduct:
    try:
        opportunity = _ensure_opportunity(session, opportunity_id)
        product = _ensure_product(session, product_id=product_input.product_id, product_code=product_input.product_code)
        if any(existing.product_code == product.code for existing in opportunity.products):
            raise DuplicateOpportunityProductError(f"Opportunity already has product {product.code}.")
        row = _build_product_row(session, opportunity, product_input)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")
    except Exception:
        session.rollback()
        raise


def update_opportunity_product(session: Session, opportunity_product_id: int, **changes) -> OpportunityProduct:
    try:
        row = session.get(OpportunityProduct, opportunity_product_id)
        if row is None:
            raise RecordNotFoundError(f"Opportunity product id={opportunity_product_id} was not found.")
        if "product_id" in changes or "product_code" in changes:
            product = _ensure_product(
                session,
                product_id=changes.get("product_id"),
                product_code=changes.get("product_code"),
            )
            duplicate = session.scalar(
                select(OpportunityProduct).where(
                    OpportunityProduct.opportunity_id == row.opportunity_id,
                    OpportunityProduct.product_code == product.code,
                    OpportunityProduct.id != row.id,
                )
            )
            if duplicate is not None:
                raise DuplicateOpportunityProductError(f"Opportunity already has product {product.code}.")
            row.product = product
            row.product_code = product.code
        if "estimated_quantity" in changes:
            row.estimated_quantity = validate_nonnegative_quantity(changes["estimated_quantity"])
        if "estimated_incremental_mrr" in changes:
            row.estimated_incremental_mrr = validate_nonnegative_money(changes["estimated_incremental_mrr"])
        for field_name in ("interest_level", "notes"):
            if field_name in changes:
                setattr(row, field_name, clean_optional_text(changes[field_name]))
        session.commit()
        session.refresh(row)
        return row
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")
    except Exception:
        session.rollback()
        raise


def remove_opportunity_product(session: Session, opportunity_product_id: int) -> None:
    try:
        row = session.get(OpportunityProduct, opportunity_product_id)
        if row is None:
            raise RecordNotFoundError(f"Opportunity product id={opportunity_product_id} was not found.")
        session.delete(row)
        session.commit()
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)


def list_opportunity_products(session: Session, opportunity_id: int) -> tuple[OpportunityProduct, ...]:
    _ensure_opportunity(session, opportunity_id)
    rows = session.scalars(
        select(OpportunityProduct)
        .options(selectinload(OpportunityProduct.product))
        .where(OpportunityProduct.opportunity_id == opportunity_id)
        .order_by(OpportunityProduct.id)
    ).all()
    return tuple(rows)


def list_opportunities(
    session: Session,
    *,
    company_id: Optional[int] = None,
    location_id: Optional[int] = None,
    stage: OpportunityStage | str | None = None,
    active_only: bool = True,
    include_archived: bool = False,
    follow_up_due_before: Optional[date] = None,
    expected_close_start: Optional[date] = None,
    expected_close_end: Optional[date] = None,
    minimum_priority_score: Optional[int] = None,
    product_id: Optional[int] = None,
    product_code: Optional[str] = None,
    today: Optional[date] = None,
) -> tuple[Opportunity, ...]:
    today_value = today or date.today()
    query = (
        select(Opportunity)
        .options(
            selectinload(Opportunity.company),
            selectinload(Opportunity.location),
            selectinload(Opportunity.primary_contact),
            selectinload(Opportunity.products).selectinload(OpportunityProduct.product),
        )
    )
    if active_only and not include_archived:
        query = query.where(Opportunity.is_active.is_(True))
    if company_id is not None:
        query = query.where(Opportunity.company_id == company_id)
    if location_id is not None:
        query = query.where(Opportunity.location_id == location_id)
    if stage is not None:
        query = query.where(Opportunity.stage == normalize_opportunity_stage(stage))
    if follow_up_due_before is not None:
        query = query.where(Opportunity.next_action_date <= follow_up_due_before)
    if expected_close_start is not None:
        query = query.where(Opportunity.expected_close_date >= expected_close_start)
    if expected_close_end is not None:
        query = query.where(Opportunity.expected_close_date <= expected_close_end)
    if minimum_priority_score is not None:
        query = query.where(Opportunity.priority_score >= validate_score(minimum_priority_score, "Minimum priority score"))
    if product_id is not None or product_code is not None:
        product_filter = exists().where(OpportunityProduct.opportunity_id == Opportunity.id)
        if product_id is not None:
            product_filter = product_filter.where(OpportunityProduct.product_id == product_id)
        if product_code is not None:
            product_filter = product_filter.where(OpportunityProduct.product_code == product_code)
        query = query.where(product_filter)
    overdue_rank = case((Opportunity.next_action_date < today_value, 0), else_=1)
    null_due_rank = case((Opportunity.next_action_date.is_(None), 1), else_=0)
    query = query.order_by(overdue_rank, null_due_rank, Opportunity.next_action_date, Opportunity.priority_score.desc(), Opportunity.updated_at.desc())
    return tuple(session.scalars(query).all())


def _contact_name(contact: Optional[Contact]) -> Optional[str]:
    if contact is None:
        return None
    name = " ".join(value for value in (contact.first_name, contact.last_name) if value).strip()
    return name or contact.email or contact.phone or f"Contact {contact.id}"


def _location_name(location: Optional[Location]) -> Optional[str]:
    if location is None:
        return None
    return location.location_name or f"{location.address_line_1}, {location.city}"


def product_to_dto(row: OpportunityProduct) -> OpportunityProductDTO:
    return OpportunityProductDTO(
        id=row.id,
        opportunity_id=row.opportunity_id,
        product_id=row.product_id,
        product_code=row.product_code,
        product_name=row.product.name if row.product else row.product_code,
        estimated_quantity=row.estimated_quantity,
        estimated_incremental_mrr=money(row.estimated_incremental_mrr),
        interest_level=row.interest_level,
        notes=row.notes,
    )


def opportunity_to_summary(opportunity: Opportunity, *, today: Optional[date] = None) -> OpportunitySummary:
    today_value = today or date.today()
    products = tuple(product_to_dto(row) for row in opportunity.products)
    return OpportunitySummary(
        id=opportunity.id,
        company_id=opportunity.company_id,
        company_name=opportunity.company.name,
        location_id=opportunity.location_id,
        location_name=_location_name(opportunity.location),
        primary_contact_id=opportunity.primary_contact_id,
        primary_contact_name=_contact_name(opportunity.primary_contact),
        name=opportunity.name,
        stage=normalize_opportunity_stage(opportunity.stage),
        stage_display=stage_display(opportunity.stage),
        product_names=tuple(product.product_name for product in products),
        estimated_total_quantity=sum(product.estimated_quantity for product in products),
        estimated_mrr=money(opportunity.estimated_mrr) if opportunity.estimated_mrr is not None else None,
        internet_probability=opportunity.internet_probability,
        priority_score=opportunity.priority_score,
        next_action=opportunity.next_action,
        next_action_date=opportunity.next_action_date,
        expected_close_date=opportunity.expected_close_date,
        is_overdue=opportunity.next_action_date is not None and opportunity.next_action_date < today_value and is_open_stage(opportunity.stage),
        is_active=opportunity.is_active,
    )


def opportunity_to_detail(opportunity: Opportunity, *, today: Optional[date] = None) -> OpportunityDetail:
    return OpportunityDetail(
        summary=opportunity_to_summary(opportunity, today=today),
        notes=opportunity.notes,
        lost_reason=opportunity.lost_reason,
        revenue_potential_score=opportunity.revenue_potential_score,
        cross_sell_score=opportunity.cross_sell_score,
        score_reason=opportunity.score_reason,
        products=tuple(product_to_dto(row) for row in opportunity.products),
        created_at=opportunity.created_at,
        updated_at=opportunity.updated_at,
    )
