from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import (
    ActivityOutcome,
    ActivityType,
    ContactRole,
    LocationType,
    OpportunityStage,
    ProductType,
    ProviderType,
    SaleStatus,
    ServiceRecordType,
    ServiceStatus,
    SpectrumRelationship,
    TaskStatus,
    TaskType,
    TerritoryStatus,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


def enum_column(enum_type: type, **kwargs: object) -> SQLEnum:
    # SQLite stores these as validated strings instead of native enum types.
    return SQLEnum(enum_type, native_enum=False, validate_strings=True, **kwargs)


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(255))
    main_phone: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    industry: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    estimated_employees: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_mobile_lines: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_fleet_size: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)

    locations: Mapped[list["Location"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    services: Mapped[list["Service"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    sales: Mapped[list["Sale"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Company(id={self.id!r}, name={self.name!r})"


class Location(TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "address_line_1",
            "postal_code",
            name="uq_locations_company_address_postal",
        ),
        Index("ix_locations_city_state", "city", "state"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(255))
    address_line_1: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    address_line_2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    location_type: Mapped[LocationType] = mapped_column(enum_column(LocationType), nullable=False)
    territory_status: Mapped[TerritoryStatus] = mapped_column(
        enum_column(TerritoryStatus),
        default=TerritoryStatus.UNKNOWN,
        nullable=False,
        index=True,
    )
    spectrum_relationship: Mapped[SpectrumRelationship] = mapped_column(
        enum_column(SpectrumRelationship),
        default=SpectrumRelationship.UNKNOWN,
        nullable=False,
        index=True,
    )
    business_use_confirmed: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_primary_business_location: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    current_provider_notes: Mapped[Optional[str]] = mapped_column(Text)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)

    company: Mapped["Company"] = relationship(back_populates="locations")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="location")
    services: Mapped[list["Service"]] = relationship(back_populates="location")
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="location")
    activities: Mapped[list["Activity"]] = relationship(back_populates="location")
    tasks: Mapped[list["Task"]] = relationship(back_populates="location")
    sales: Mapped[list["Sale"]] = relationship(back_populates="location")

    def __repr__(self) -> str:
        return (
            f"Location(id={self.id!r}, company_id={self.company_id!r}, "
            f"address_line_1={self.address_line_1!r})"
        )


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        Index("ix_contacts_name", "last_name", "first_name"),
        Index("ix_contacts_company_primary", "company_id", "is_primary_contact"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(120))
    last_name: Mapped[Optional[str]] = mapped_column(String(120))
    job_title: Mapped[Optional[str]] = mapped_column(String(160))
    phone: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    decision_role: Mapped[ContactRole] = mapped_column(
        enum_column(ContactRole),
        default=ContactRole.UNKNOWN,
        nullable=False,
        index=True,
    )
    preferred_contact_method: Mapped[Optional[str]] = mapped_column(String(50))
    is_primary_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)

    company: Mapped["Company"] = relationship(back_populates="contacts")
    location: Mapped[Optional["Location"]] = relationship(back_populates="contacts")
    services: Mapped[list["Service"]] = relationship(back_populates="contact")
    primary_opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="primary_contact")
    activities: Mapped[list["Activity"]] = relationship(back_populates="contact")
    tasks: Mapped[list["Task"]] = relationship(back_populates="contact")


class Service(TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        Index("ix_services_company_product", "company_id", "product_type"),
        Index("ix_services_location_record_type", "location_id", "record_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id"), index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunities.id"), index=True)
    record_type: Mapped[ServiceRecordType] = mapped_column(
        enum_column(ServiceRecordType),
        nullable=False,
        index=True,
    )
    provider: Mapped[ProviderType] = mapped_column(enum_column(ProviderType), nullable=False, index=True)
    product_type: Mapped[ProductType] = mapped_column(enum_column(ProductType), nullable=False, index=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    service_status: Mapped[Optional[ServiceStatus]] = mapped_column(enum_column(ServiceStatus), index=True)
    current_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    potential_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    plan_name: Mapped[Optional[str]] = mapped_column(String(160))
    speed_tier: Mapped[Optional[str]] = mapped_column(String(80))
    monthly_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    contract_end_date: Mapped[Optional[date]] = mapped_column(Date)
    satisfaction_level: Mapped[Optional[str]] = mapped_column(String(80))
    pain_points: Mapped[Optional[str]] = mapped_column(Text)
    eligibility_status: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    recommended_offer: Mapped[Optional[str]] = mapped_column(Text)
    next_action: Mapped[Optional[str]] = mapped_column(String(255))
    next_action_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(120))
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)

    company: Mapped["Company"] = relationship(back_populates="services")
    location: Mapped["Location"] = relationship(back_populates="services")
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="services")
    opportunity: Mapped[Optional["Opportunity"]] = relationship(back_populates="services")


class Opportunity(TimestampMixin, Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint("internet_probability BETWEEN 0 AND 100", name="ck_opportunities_internet_probability"),
        CheckConstraint("revenue_potential_score BETWEEN 0 AND 100", name="ck_opportunities_revenue_score"),
        CheckConstraint("cross_sell_score BETWEEN 0 AND 100", name="ck_opportunities_cross_sell_score"),
        CheckConstraint("priority_score BETWEEN 0 AND 100", name="ck_opportunities_priority_score"),
        Index("ix_opportunities_company_stage", "company_id", "stage"),
        Index("ix_opportunities_location_stage", "location_id", "stage"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    primary_contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[OpportunityStage] = mapped_column(
        enum_column(OpportunityStage),
        default=OpportunityStage.NEW,
        nullable=False,
        index=True,
    )
    primary_product: Mapped[Optional[ProductType]] = mapped_column(enum_column(ProductType), index=True)
    internet_probability: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revenue_potential_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cross_sell_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_internet_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_mobile_lines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_voice_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_video_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_mrr: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    expected_close_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    next_action: Mapped[Optional[str]] = mapped_column(String(255))
    next_action_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    lost_reason: Mapped[Optional[str]] = mapped_column(Text)
    score_reason: Mapped[Optional[str]] = mapped_column(Text)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)

    company: Mapped["Company"] = relationship(back_populates="opportunities")
    location: Mapped["Location"] = relationship(back_populates="opportunities")
    primary_contact: Mapped[Optional["Contact"]] = relationship(back_populates="primary_opportunities")
    services: Mapped[list["Service"]] = relationship(back_populates="opportunity")
    activities: Mapped[list["Activity"]] = relationship(back_populates="opportunity")
    tasks: Mapped[list["Task"]] = relationship(back_populates="opportunity")
    sales: Mapped[list["Sale"]] = relationship(back_populates="opportunity")

    def __repr__(self) -> str:
        return f"Opportunity(id={self.id!r}, name={self.name!r}, stage={self.stage!r})"


class Activity(TimestampMixin, Base):
    __tablename__ = "activities"
    __table_args__ = (
        Index("ix_activities_company_activity_at", "company_id", "activity_at"),
        Index("ix_activities_opportunity_activity_at", "opportunity_id", "activity_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id"), index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunities.id"), index=True)
    activity_type: Mapped[ActivityType] = mapped_column(enum_column(ActivityType), nullable=False, index=True)
    activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    outcome: Mapped[Optional[ActivityOutcome]] = mapped_column(enum_column(ActivityOutcome), index=True)
    disposition: Mapped[Optional[str]] = mapped_column(String(120))
    products_discussed: Mapped[Optional[str]] = mapped_column(Text)
    current_provider_notes: Mapped[Optional[str]] = mapped_column(Text)
    pain_points: Mapped[Optional[str]] = mapped_column(Text)
    objections: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)

    company: Mapped["Company"] = relationship(back_populates="activities")
    location: Mapped[Optional["Location"]] = relationship(back_populates="activities")
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="activities")
    opportunity: Mapped[Optional["Opportunity"]] = relationship(back_populates="activities")


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_company_status_due", "company_id", "status", "due_at"),
        Index("ix_tasks_opportunity_status", "opportunity_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"), index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id"), index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunities.id"), index=True)
    task_type: Mapped[TaskType] = mapped_column(enum_column(TaskType), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    priority: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    status: Mapped[TaskStatus] = mapped_column(
        enum_column(TaskStatus),
        default=TaskStatus.OPEN,
        nullable=False,
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    company: Mapped["Company"] = relationship(back_populates="tasks")
    location: Mapped[Optional["Location"]] = relationship(back_populates="tasks")
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="tasks")
    opportunity: Mapped[Optional["Opportunity"]] = relationship(back_populates="tasks")


class Sale(TimestampMixin, Base):
    __tablename__ = "sales"
    __table_args__ = (
        Index("ix_sales_company_order_date", "company_id", "order_date"),
        Index("ix_sales_location_status", "location_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunities.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[SaleStatus] = mapped_column(
        enum_column(SaleStatus),
        default=SaleStatus.SUBMITTED,
        nullable=False,
        index=True,
    )
    scheduled_install_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    actual_install_date: Mapped[Optional[date]] = mapped_column(Date)
    total_mrr: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    opportunity: Mapped[Optional["Opportunity"]] = relationship(back_populates="sales")
    company: Mapped["Company"] = relationship(back_populates="sales")
    location: Mapped["Location"] = relationship(back_populates="sales")
    sale_items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Sale(id={self.id!r}, company_id={self.company_id!r}, status={self.status!r})"


class SaleItem(TimestampMixin, Base):
    __tablename__ = "sale_items"
    __table_args__ = (Index("ix_sale_items_sale_product", "sale_id", "product_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), nullable=False, index=True)
    product_type: Mapped[ProductType] = mapped_column(enum_column(ProductType), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    installed_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activation_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(String(80), index=True)

    sale: Mapped["Sale"] = relationship(back_populates="sale_items")
