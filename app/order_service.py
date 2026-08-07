from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import exists, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.crud import RecordNotFoundError
from app.enums import OpportunityStage, ProductType, SaleStatus
from app.models import Company, Contact, Location, Opportunity, OpportunityProduct, Product, Sale, SaleItem
from app.validation import clean_optional_text


MONEY_QUANT = Decimal("0.01")
ORDER_STATUS_LABELS = {
    SaleStatus.DRAFT: "Draft",
    SaleStatus.SUBMITTED: "Submitted",
    SaleStatus.SCHEDULED: "Scheduled",
    SaleStatus.PARTIALLY_FULFILLED: "Partially Fulfilled",
    SaleStatus.FULFILLED: "Fulfilled",
    SaleStatus.CANCELED: "Canceled",
    SaleStatus.INSTALLED: "Installed (Legacy)",
    SaleStatus.DISCONNECTED: "Disconnected (Legacy)",
}
LEGACY_ORDER_STATUS_MAP = {
    "CANCELLED": SaleStatus.CANCELED,
    "CANCELED": SaleStatus.CANCELED,
}
PRODUCT_TYPE_BY_CODE = {
    "BUSINESS_INTERNET": ProductType.INTERNET,
    "BUSINESS_MOBILE": ProductType.MOBILE,
    "BUSINESS_VOICE": ProductType.VOICE,
    "BUSINESS_VIDEO": ProductType.VIDEO,
    "SEASONAL_SPORTS": ProductType.VIDEO,
    "EVERPASS": ProductType.VIDEO,
    "MANAGED_WIFI": ProductType.WIFI,
    "SECURITY": ProductType.OTHER,
    "WIB": ProductType.BACKUP_INTERNET,
    "INVINCIBLE_WIFI": ProductType.WIFI,
    "UNLIMITED_PLUS": ProductType.MOBILE,
    "OTHER": ProductType.OTHER,
}


class OrderError(Exception):
    """Base error for sales order service operations."""


class OrderValidationError(OrderError):
    """Raised when an order violates backend validation rules."""


class DuplicateOrderItemError(OrderValidationError):
    """Raised when an order contains duplicate product rows."""


@dataclass(frozen=True)
class OrderItemInput:
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    quantity: int = 1
    incremental_mrr: Decimal = Decimal("0.00")
    notes: Optional[str] = None
    source_opportunity_product_id: Optional[int] = None


@dataclass(frozen=True)
class OrderItemDraft:
    opportunity_product_id: Optional[int]
    product_id: int
    product_code: str
    product_name: str
    quantity: int
    incremental_mrr: Decimal
    notes: Optional[str]


@dataclass(frozen=True)
class OpportunityOrderPreview:
    opportunity_id: int
    opportunity_name: str
    company_id: int
    company_name: str
    location_id: Optional[int]
    location_name: Optional[str]
    primary_contact_id: Optional[int]
    primary_contact_name: Optional[str]
    suggested_order_date: date
    suggested_items: tuple[OrderItemDraft, ...]
    estimated_total_quantity: int
    estimated_total_mrr: Decimal


@dataclass(frozen=True)
class CreatedOrderResult:
    order_id: int
    company_id: int
    company_name: str
    opportunity_id: Optional[int]
    opportunity_name: Optional[str]
    order_date: date
    status: SaleStatus
    item_count: int
    total_quantity: int
    total_incremental_mrr: Decimal


@dataclass(frozen=True)
class OrderItemDTO:
    id: int
    order_id: int
    product_id: Optional[int]
    product_code: str
    product_name: str
    quantity: int
    incremental_mrr: Decimal
    notes: Optional[str]
    source_opportunity_product_id: Optional[int]


@dataclass(frozen=True)
class OrderSummary:
    order_id: int
    order_date: date
    company_id: int
    company_name: str
    location_id: Optional[int]
    location_name: Optional[str]
    contact_id: Optional[int]
    contact_name: Optional[str]
    opportunity_id: Optional[int]
    opportunity_name: Optional[str]
    status: SaleStatus
    status_display: str
    product_names: tuple[str, ...]
    item_count: int
    total_quantity: int
    total_incremental_mrr: Decimal
    external_order_number: Optional[str]


@dataclass(frozen=True)
class OrderDetail:
    summary: OrderSummary
    notes: Optional[str]
    customer_account_reference: Optional[str]
    submitted_at: Optional[datetime]
    items: tuple[OrderItemDTO, ...]
    created_at: datetime
    updated_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def money(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def normalize_order_status(status: SaleStatus | str | None) -> SaleStatus:
    if status is None:
        raise OrderValidationError("Order status is required.")
    if isinstance(status, SaleStatus):
        return status
    raw = str(status).strip().upper()
    mapped = LEGACY_ORDER_STATUS_MAP.get(raw)
    if mapped is not None:
        return mapped
    try:
        return SaleStatus(raw)
    except ValueError as exc:
        raise OrderValidationError(f"Unsupported order status: {status}.") from exc


def order_status_display(status: SaleStatus | str) -> str:
    normalized = normalize_order_status(status)
    return ORDER_STATUS_LABELS.get(normalized, normalized.value.replace("_", " ").title())


def is_order_open(status: SaleStatus | str) -> bool:
    return normalize_order_status(status) in {SaleStatus.DRAFT, SaleStatus.SUBMITTED, SaleStatus.SCHEDULED}


def is_order_canceled(status: SaleStatus | str) -> bool:
    return normalize_order_status(status) == SaleStatus.CANCELED


def is_order_legacy_commission_eligible(status: SaleStatus | str) -> bool:
    return normalize_order_status(status) == SaleStatus.INSTALLED


def validate_order_date(order_date: Optional[date]) -> date:
    if order_date is None:
        raise OrderValidationError("Order date is required.")
    return order_date


def validate_order_item_quantity(quantity: int) -> int:
    if quantity <= 0:
        raise OrderValidationError("Ordered quantity must be greater than zero.")
    return quantity


def validate_order_item_mrr(value: Decimal | int | str | None) -> Decimal:
    amount = money(value)
    if amount < Decimal("0.00"):
        raise OrderValidationError("Incremental MRR cannot be negative.")
    return amount


def validate_external_order_number(value: Optional[str]) -> Optional[str]:
    return clean_optional_text(value)


def validate_order_has_items(items: list[OrderItemInput]) -> None:
    if not items:
        raise OrderValidationError("Select at least one product.")


def _handle_db_error(session: Session, error: SQLAlchemyError) -> None:
    session.rollback()
    raise OrderError("Order database operation failed.") from error


def _ensure_company(session: Session, company_id: int, *, require_active: bool = False) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise RecordNotFoundError(f"Company id={company_id} was not found.")
    if require_active and not company.is_active:
        raise OrderValidationError(f"Company id={company_id} is inactive.")
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
        raise OrderValidationError("Selected location does not belong to the company.")
    if require_active and not location.is_active:
        raise OrderValidationError(f"Location id={location_id} is inactive.")
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
        raise OrderValidationError("Selected contact does not belong to the company.")
    if require_active and not contact.is_active:
        raise OrderValidationError(f"Contact id={contact_id} is inactive.")
    return contact


def _ensure_opportunity(session: Session, opportunity_id: Optional[int], *, company_id: int) -> Optional[Opportunity]:
    if opportunity_id is None:
        return None
    opportunity = session.get(
        Opportunity,
        opportunity_id,
        options=(
            selectinload(Opportunity.company),
            selectinload(Opportunity.location),
            selectinload(Opportunity.primary_contact),
            selectinload(Opportunity.products).selectinload(OpportunityProduct.product),
        ),
    )
    if opportunity is None:
        raise RecordNotFoundError(f"Opportunity id={opportunity_id} was not found.")
    if opportunity.company_id != company_id:
        raise OrderValidationError("Selected opportunity does not belong to the company.")
    return opportunity


def _load_order(session: Session, order_id: int) -> Sale:
    order = session.scalar(
        select(Sale)
        .options(
            selectinload(Sale.company),
            selectinload(Sale.location),
            selectinload(Sale.contact),
            selectinload(Sale.opportunity),
            selectinload(Sale.sale_items).selectinload(SaleItem.product),
        )
        .where(Sale.id == order_id)
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise RecordNotFoundError(f"Order id={order_id} was not found.")
    return order


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
        raise OrderValidationError("Inactive products cannot be added to a new order.")
    return product


def _product_type_for_product(product: Product) -> ProductType:
    return PRODUCT_TYPE_BY_CODE.get(product.code, ProductType.OTHER)


def _build_order_item(session: Session, order: Sale, item_input: OrderItemInput) -> SaleItem:
    product = _ensure_product(session, product_id=item_input.product_id, product_code=item_input.product_code)
    return SaleItem(
        sale=order,
        product=product,
        product_type=_product_type_for_product(product),
        quantity=validate_order_item_quantity(item_input.quantity),
        incremental_mrr=validate_order_item_mrr(item_input.incremental_mrr),
        monthly_revenue=validate_order_item_mrr(item_input.incremental_mrr),
        notes=clean_optional_text(item_input.notes),
        source_opportunity_product_id=item_input.source_opportunity_product_id,
    )


def _validate_no_duplicate_products(items: list[SaleItem]) -> None:
    seen: set[int] = set()
    for item in items:
        product_id = item.product_id if item.product_id is not None else item.product.id if item.product else None
        if product_id in seen:
            raise DuplicateOrderItemError("This product is already included in the order.")
        if product_id is not None:
            seen.add(product_id)


def _contact_name(contact: Optional[Contact]) -> Optional[str]:
    if contact is None:
        return None
    name = " ".join(value for value in (contact.first_name, contact.last_name) if value).strip()
    return name or contact.email or contact.phone or f"Contact {contact.id}"


def _location_name(location: Optional[Location]) -> Optional[str]:
    if location is None:
        return None
    return location.location_name or f"{location.address_line_1}, {location.city}"


def _sale_item_mrr(item: SaleItem) -> Decimal:
    return money(item.incremental_mrr if item.incremental_mrr is not None else item.monthly_revenue)


def order_item_to_dto(item: SaleItem) -> OrderItemDTO:
    product_code = item.product.code if item.product else item.product_type.value
    product_name = item.product.name if item.product else product_code
    return OrderItemDTO(
        id=item.id,
        order_id=item.sale_id,
        product_id=item.product_id,
        product_code=product_code,
        product_name=product_name,
        quantity=item.quantity,
        incremental_mrr=_sale_item_mrr(item),
        notes=item.notes,
        source_opportunity_product_id=item.source_opportunity_product_id,
    )


def order_to_summary(order: Sale) -> OrderSummary:
    items = tuple(order_item_to_dto(item) for item in order.sale_items)
    return OrderSummary(
        order_id=order.id,
        order_date=order.order_date,
        company_id=order.company_id,
        company_name=order.company.name,
        location_id=order.location_id,
        location_name=_location_name(order.location),
        contact_id=order.contact_id,
        contact_name=_contact_name(order.contact),
        opportunity_id=order.opportunity_id,
        opportunity_name=order.opportunity.name if order.opportunity else None,
        status=normalize_order_status(order.status),
        status_display=order_status_display(order.status),
        product_names=tuple(item.product_name for item in items),
        item_count=len(items),
        total_quantity=sum(item.quantity for item in items),
        total_incremental_mrr=money(sum((item.incremental_mrr for item in items), Decimal("0.00"))),
        external_order_number=order.external_order_number,
    )


def order_to_detail(order: Sale) -> OrderDetail:
    return OrderDetail(
        summary=order_to_summary(order),
        notes=order.notes,
        customer_account_reference=order.customer_account_reference,
        submitted_at=order.submitted_at,
        items=tuple(order_item_to_dto(item) for item in order.sale_items),
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def order_to_created_result(order: Sale) -> CreatedOrderResult:
    summary = order_to_summary(order)
    return CreatedOrderResult(
        order_id=summary.order_id,
        company_id=summary.company_id,
        company_name=summary.company_name,
        opportunity_id=summary.opportunity_id,
        opportunity_name=summary.opportunity_name,
        order_date=summary.order_date,
        status=summary.status,
        item_count=summary.item_count,
        total_quantity=summary.total_quantity,
        total_incremental_mrr=summary.total_incremental_mrr,
    )


def create_order(
    session: Session,
    *,
    company_id: int,
    order_date: date,
    status: SaleStatus | str = SaleStatus.DRAFT,
    location_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    external_order_number: Optional[str] = None,
    customer_account_reference: Optional[str] = None,
    submitted_at: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> Sale:
    try:
        company = _ensure_company(session, company_id, require_active=True)
        location = _ensure_location(session, location_id, company_id=company.id, require_active=True)
        contact = _ensure_contact(session, contact_id, company_id=company.id, require_active=True)
        opportunity = _ensure_opportunity(session, opportunity_id, company_id=company.id)
        order = Sale(
            company=company,
            location=location,
            contact=contact,
            opportunity=opportunity,
            order_date=validate_order_date(order_date),
            status=normalize_order_status(status),
            external_order_number=validate_external_order_number(external_order_number),
            customer_account_reference=clean_optional_text(customer_account_reference),
            submitted_at=submitted_at,
            notes=clean_optional_text(notes),
        )
        session.add(order)
        session.commit()
        return _load_order(session, order.id)
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")
    except Exception:
        session.rollback()
        raise


def create_order_with_items(
    session: Session,
    *,
    company_id: int,
    order_date: date,
    items: list[OrderItemInput],
    status: SaleStatus | str = SaleStatus.DRAFT,
    location_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    external_order_number: Optional[str] = None,
    customer_account_reference: Optional[str] = None,
    submitted_at: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> CreatedOrderResult:
    try:
        validate_order_has_items(items)
        company = _ensure_company(session, company_id, require_active=True)
        location = _ensure_location(session, location_id, company_id=company.id, require_active=True)
        contact = _ensure_contact(session, contact_id, company_id=company.id, require_active=True)
        opportunity = _ensure_opportunity(session, opportunity_id, company_id=company.id)
        order = Sale(
            company=company,
            location=location,
            contact=contact,
            opportunity=opportunity,
            order_date=validate_order_date(order_date),
            status=normalize_order_status(status),
            external_order_number=validate_external_order_number(external_order_number),
            customer_account_reference=clean_optional_text(customer_account_reference),
            submitted_at=submitted_at,
            notes=clean_optional_text(notes),
        )
        order.sale_items = [_build_order_item(session, order, item) for item in items]
        _validate_no_duplicate_products(order.sale_items)
        order.total_mrr = money(sum((_sale_item_mrr(item) for item in order.sale_items), Decimal("0.00")))
        session.add(order)
        session.commit()
        return order_to_created_result(_load_order(session, order.id))
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")
    except Exception:
        session.rollback()
        raise


def build_order_preview_from_opportunity(session: Session, opportunity_id: int) -> OpportunityOrderPreview:
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
    if not opportunity.company.is_active:
        raise OrderValidationError(f"Company id={opportunity.company_id} is inactive.")
    suggested_items = tuple(
        OrderItemDraft(
            opportunity_product_id=row.id,
            product_id=row.product_id,
            product_code=row.product.code,
            product_name=row.product.name,
            quantity=row.estimated_quantity,
            incremental_mrr=money(row.estimated_incremental_mrr),
            notes=row.notes,
        )
        for row in opportunity.products
        if row.product is not None and row.product_id is not None
    )
    return OpportunityOrderPreview(
        opportunity_id=opportunity.id,
        opportunity_name=opportunity.name,
        company_id=opportunity.company_id,
        company_name=opportunity.company.name,
        location_id=opportunity.location_id,
        location_name=_location_name(opportunity.location),
        primary_contact_id=opportunity.primary_contact_id,
        primary_contact_name=_contact_name(opportunity.primary_contact),
        suggested_order_date=date.today(),
        suggested_items=suggested_items,
        estimated_total_quantity=sum(item.quantity for item in suggested_items),
        estimated_total_mrr=money(sum((item.incremental_mrr for item in suggested_items), Decimal("0.00"))),
    )


def create_order_from_opportunity(
    session: Session,
    *,
    opportunity_id: int,
    order_date: date,
    status: SaleStatus | str,
    item_inputs: list[OrderItemInput],
    location_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    external_order_number: Optional[str] = None,
    customer_account_reference: Optional[str] = None,
    submitted_at: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> CreatedOrderResult:
    opportunity = session.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise RecordNotFoundError(f"Opportunity id={opportunity_id} was not found.")
    return create_order_with_items(
        session,
        company_id=opportunity.company_id,
        location_id=location_id if location_id is not None else opportunity.location_id,
        contact_id=contact_id if contact_id is not None else opportunity.primary_contact_id,
        opportunity_id=opportunity.id,
        order_date=order_date,
        status=status,
        items=item_inputs,
        external_order_number=external_order_number,
        customer_account_reference=customer_account_reference,
        submitted_at=submitted_at,
        notes=notes,
    )


def get_order(session: Session, order_id: int) -> OrderDetail:
    return order_to_detail(_load_order(session, order_id))


def list_orders(
    session: Session,
    *,
    company_id: Optional[int] = None,
    location_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    status: SaleStatus | str | None = None,
    order_date_start: Optional[date] = None,
    order_date_end: Optional[date] = None,
    product_id: Optional[int] = None,
    product_code: Optional[str] = None,
    external_order_number: Optional[str] = None,
) -> tuple[OrderSummary, ...]:
    query = select(Sale).options(
        selectinload(Sale.company),
        selectinload(Sale.location),
        selectinload(Sale.contact),
        selectinload(Sale.opportunity),
        selectinload(Sale.sale_items).selectinload(SaleItem.product),
    )
    if company_id is not None:
        query = query.where(Sale.company_id == company_id)
    if location_id is not None:
        query = query.where(Sale.location_id == location_id)
    if contact_id is not None:
        query = query.where(Sale.contact_id == contact_id)
    if opportunity_id is not None:
        query = query.where(Sale.opportunity_id == opportunity_id)
    if status is not None:
        query = query.where(Sale.status == normalize_order_status(status))
    if order_date_start is not None:
        query = query.where(Sale.order_date >= order_date_start)
    if order_date_end is not None:
        query = query.where(Sale.order_date <= order_date_end)
    if external_order_number is not None:
        query = query.where(Sale.external_order_number.contains(external_order_number.strip()))
    if product_id is not None or product_code is not None:
        product_filter = exists().where(SaleItem.sale_id == Sale.id)
        if product_id is not None:
            product_filter = product_filter.where(SaleItem.product_id == product_id)
        if product_code is not None:
            product_filter = product_filter.where(
                SaleItem.product_id == Product.id,
                Product.code == product_code,
            )
        query = query.where(product_filter)
    query = query.order_by(Sale.order_date.desc(), Sale.created_at.desc())
    return tuple(order_to_summary(order) for order in session.scalars(query).all())


def update_order(session: Session, order_id: int, **changes) -> OrderDetail:
    try:
        if "company_id" in changes:
            raise OrderValidationError("Company cannot be changed after order creation.")
        if "opportunity_id" in changes:
            raise OrderValidationError("Opportunity source cannot be changed after order creation.")
        order = _load_order(session, order_id)
        if "location_id" in changes:
            _ensure_location(session, changes["location_id"], company_id=order.company_id, require_active=True)
            order.location_id = changes["location_id"]
        if "contact_id" in changes:
            _ensure_contact(session, changes["contact_id"], company_id=order.company_id, require_active=True)
            order.contact_id = changes["contact_id"]
        if "status" in changes:
            order.status = normalize_order_status(changes["status"])
        if "order_date" in changes:
            order.order_date = validate_order_date(changes["order_date"])
        if "external_order_number" in changes:
            order.external_order_number = validate_external_order_number(changes["external_order_number"])
        if "customer_account_reference" in changes:
            order.customer_account_reference = clean_optional_text(changes["customer_account_reference"])
        if "submitted_at" in changes:
            order.submitted_at = changes["submitted_at"]
        if "notes" in changes:
            order.notes = clean_optional_text(changes["notes"])
        session.commit()
        return order_to_detail(_load_order(session, order.id))
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")
    except Exception:
        session.rollback()
        raise


def add_order_item(session: Session, order_id: int, item_input: OrderItemInput) -> OrderItemDTO:
    try:
        order = _load_order(session, order_id)
        item = _build_order_item(session, order, item_input)
        product_id = item.product_id if item.product_id is not None else item.product.id if item.product else None
        if any(existing.product_id == product_id for existing in order.sale_items):
            raise DuplicateOrderItemError("This product is already included in the order.")
        session.add(item)
        session.commit()
        return order_item_to_dto(session.get(SaleItem, item.id, options=(selectinload(SaleItem.product),)))
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")
    except Exception:
        session.rollback()
        raise


def update_order_item(session: Session, order_item_id: int, **changes) -> OrderItemDTO:
    try:
        item = session.get(SaleItem, order_item_id, options=(selectinload(SaleItem.product),))
        if item is None:
            raise RecordNotFoundError(f"Order item id={order_item_id} was not found.")
        if "product_id" in changes or "product_code" in changes:
            product = _ensure_product(session, product_id=changes.get("product_id"), product_code=changes.get("product_code"))
            duplicate = session.scalar(
                select(SaleItem).where(
                    SaleItem.sale_id == item.sale_id,
                    SaleItem.product_id == product.id,
                    SaleItem.id != item.id,
                )
            )
            if duplicate is not None:
                raise DuplicateOrderItemError("This product is already included in the order.")
            item.product = product
            item.product_type = _product_type_for_product(product)
        if "quantity" in changes:
            item.quantity = validate_order_item_quantity(changes["quantity"])
        if "incremental_mrr" in changes:
            item.incremental_mrr = validate_order_item_mrr(changes["incremental_mrr"])
            item.monthly_revenue = item.incremental_mrr
        if "notes" in changes:
            item.notes = clean_optional_text(changes["notes"])
        session.commit()
        return order_item_to_dto(session.get(SaleItem, item.id, options=(selectinload(SaleItem.product),)))
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)
        raise AssertionError("unreachable")
    except Exception:
        session.rollback()
        raise


def remove_order_item(session: Session, order_item_id: int) -> None:
    try:
        item = session.get(SaleItem, order_item_id)
        if item is None:
            raise RecordNotFoundError(f"Order item id={order_item_id} was not found.")
        session.delete(item)
        session.commit()
    except SQLAlchemyError as exc:
        _handle_db_error(session, exc)


def list_order_items(session: Session, order_id: int) -> tuple[OrderItemDTO, ...]:
    _load_order(session, order_id)
    rows = session.scalars(
        select(SaleItem)
        .options(selectinload(SaleItem.product))
        .where(SaleItem.sale_id == order_id)
        .order_by(SaleItem.id)
    ).all()
    return tuple(order_item_to_dto(row) for row in rows)
