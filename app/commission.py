from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import CommissionPlan, CommissionTier, Product


MONEY = Decimal("0.01")
ZERO = Decimal("0.00")

TIER_RATE_BY_PRODUCT_CODE = {
    "BUSINESS_INTERNET": "internet_rate",
    "BUSINESS_MOBILE": "mobile_rate",
    "BUSINESS_VOICE": "voice_rate",
    "BUSINESS_VIDEO": "video_rate",
}


@dataclass(frozen=True)
class CommissionLineInput:
    product_code: str
    quantity: int
    incremental_mrr: Decimal


@dataclass(frozen=True)
class CommissionInput:
    internet_connects: int
    lines: tuple[CommissionLineInput, ...]


@dataclass(frozen=True)
class CommissionComponent:
    product_code: str
    quantity: int
    rate: Decimal
    payout: Decimal


@dataclass(frozen=True)
class CommissionResult:
    commission_plan_name: str
    tier_name: Optional[str]
    threshold_reached: bool
    internet_connects: int
    connected_units: int
    bonus_eligible: bool
    tiered_components: tuple[CommissionComponent, ...]
    a_la_carte_components: tuple[CommissionComponent, ...]
    total_incremental_mrr: Decimal
    mrr_percentage: Decimal
    mrr_payout: Decimal
    tiered_earnings: Decimal
    a_la_carte_earnings: Decimal
    bonus_base: Decimal
    bonus_percentage: Decimal
    bonus_payout: Decimal
    ramp_amount: Decimal
    estimated_payout: Decimal
    locked_payout: Decimal
    next_tier_name: Optional[str]
    internet_needed_for_next_tier: Optional[int]
    projected_next_tier_payout: Optional[Decimal]
    increase_if_next_tier_reached: Optional[Decimal]


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY)


def percent(value: Decimal) -> Decimal:
    return value / Decimal("100")


def get_active_commission_plan(session: Session, as_of_date: date) -> CommissionPlan:
    plans = session.scalars(
        select(CommissionPlan).where(
            CommissionPlan.active.is_(True),
            CommissionPlan.effective_start <= as_of_date,
            or_(CommissionPlan.effective_end.is_(None), CommissionPlan.effective_end >= as_of_date),
        )
    ).all()
    if not plans:
        raise ValueError(f"No active commission plan found for {as_of_date.isoformat()}.")
    if len(plans) > 1:
        plan_names = ", ".join(plan.name for plan in plans)
        raise ValueError(f"Multiple active commission plans found for {as_of_date.isoformat()}: {plan_names}.")
    return plans[0]


def get_tier_for_internet_count(plan: CommissionPlan, count: int) -> Optional[CommissionTier]:
    for tier in sorted(plan.tiers, key=lambda item: item.display_order):
        if tier.minimum_internet <= count and (tier.maximum_internet is None or count <= tier.maximum_internet):
            return tier
    return None


def get_next_tier(plan: CommissionPlan, count: int) -> Optional[CommissionTier]:
    for tier in sorted(plan.tiers, key=lambda item: item.display_order):
        if count < tier.minimum_internet:
            return tier
        if tier.maximum_internet is not None and count <= tier.maximum_internet:
            continue
    return None


def get_products_by_code(session: Session, codes: set[str]) -> dict[str, Product]:
    products = session.scalars(select(Product).where(Product.code.in_(codes), Product.active.is_(True))).all()
    products_by_code = {product.code: product for product in products}
    missing_codes = sorted(codes - set(products_by_code))
    if missing_codes:
        raise ValueError(f"Unknown or inactive product code(s): {', '.join(missing_codes)}.")
    return products_by_code


def validate_input(commission_input: CommissionInput) -> None:
    if commission_input.internet_connects < 0:
        raise ValueError("Internet connects cannot be negative.")
    for line in commission_input.lines:
        if line.quantity < 0:
            raise ValueError(f"Quantity cannot be negative for product {line.product_code}.")
        if line.incremental_mrr < ZERO:
            raise ValueError(f"Incremental MRR cannot be negative for product {line.product_code}.")


def connected_units_for_lines(
    lines: tuple[CommissionLineInput, ...],
    products_by_code: dict[str, Product],
) -> int:
    return sum(line.quantity for line in lines if products_by_code[line.product_code].counts_as_connected_unit)


def adjusted_lines_for_internet_target(
    lines: tuple[CommissionLineInput, ...],
    products_by_code: dict[str, Product],
    additional_internet: int,
) -> tuple[CommissionLineInput, ...]:
    if additional_internet <= 0:
        return lines

    adjusted_lines: list[CommissionLineInput] = []
    added = False
    for line in lines:
        if not added and products_by_code[line.product_code].counts_as_internet_connect:
            adjusted_lines.append(
                CommissionLineInput(
                    product_code=line.product_code,
                    quantity=line.quantity + additional_internet,
                    incremental_mrr=line.incremental_mrr,
                )
            )
            added = True
        else:
            adjusted_lines.append(line)

    if not added:
        adjusted_lines.append(
            CommissionLineInput(
                product_code="BUSINESS_INTERNET",
                quantity=additional_internet,
                incremental_mrr=ZERO,
            )
        )
    return tuple(adjusted_lines)


def payable_components(
    lines: tuple[CommissionLineInput, ...],
    products_by_code: dict[str, Product],
    tier: CommissionTier,
) -> tuple[
    tuple[CommissionComponent, ...],
    tuple[CommissionComponent, ...],
    Decimal,
    Decimal,
    Decimal,
    Decimal,
]:
    tiered_components: list[CommissionComponent] = []
    a_la_carte_components: list[CommissionComponent] = []
    total_incremental_mrr = money(sum((line.incremental_mrr for line in lines), ZERO))

    for line in lines:
        product = products_by_code[line.product_code]
        if product.uses_tiered_rates:
            rate_field = TIER_RATE_BY_PRODUCT_CODE.get(product.code)
            if rate_field is None:
                raise ValueError(f"No tier rate mapping configured for tiered product {product.code}.")
            rate = money(getattr(tier, rate_field))
            tiered_components.append(
                CommissionComponent(
                    product_code=product.code,
                    quantity=line.quantity,
                    rate=rate,
                    payout=money(rate * line.quantity),
                )
            )
        if product.uses_flat_rate:
            if product.flat_commission_amount is None:
                raise ValueError(f"Flat-rate product {product.code} has no flat commission amount.")
            rate = money(product.flat_commission_amount)
            a_la_carte_components.append(
                CommissionComponent(
                    product_code=product.code,
                    quantity=line.quantity,
                    rate=rate,
                    payout=money(rate * line.quantity),
                )
            )

    tiered_earnings = money(sum((component.payout for component in tiered_components), ZERO))
    a_la_carte_earnings = money(sum((component.payout for component in a_la_carte_components), ZERO))
    mrr_payout = money(total_incremental_mrr * percent(tier.mrr_percentage))

    return (
        tuple(tiered_components),
        tuple(a_la_carte_components),
        total_incremental_mrr,
        mrr_payout,
        tiered_earnings,
        a_la_carte_earnings,
    )


def payout_for_tier(
    lines: tuple[CommissionLineInput, ...],
    products_by_code: dict[str, Product],
    plan: CommissionPlan,
    tier: CommissionTier,
) -> tuple[
    tuple[CommissionComponent, ...],
    tuple[CommissionComponent, ...],
    Decimal,
    Decimal,
    Decimal,
    Decimal,
    Decimal,
    Decimal,
    Decimal,
]:
    (
        tiered_components,
        a_la_carte_components,
        total_incremental_mrr,
        mrr_payout,
        tiered_earnings,
        a_la_carte_earnings,
    ) = payable_components(lines, products_by_code, tier)

    connected_units = connected_units_for_lines(lines, products_by_code)
    bonus_base = money(tiered_earnings + a_la_carte_earnings)
    bonus_payout = ZERO
    if connected_units >= plan.bonus_unit_threshold:
        bonus_payout = money(bonus_base * percent(plan.bonus_percentage))
    ramp_amount = ZERO
    payout = money(tiered_earnings + a_la_carte_earnings + mrr_payout + bonus_payout + ramp_amount)
    return (
        tiered_components,
        a_la_carte_components,
        total_incremental_mrr,
        mrr_payout,
        tiered_earnings,
        a_la_carte_earnings,
        bonus_base,
        bonus_payout,
        payout,
    )


def calculate_commission(
    session: Session,
    commission_input: CommissionInput,
    as_of_date: Optional[date] = None,
) -> CommissionResult:
    validate_input(commission_input)
    calculation_date = as_of_date or date.today()
    plan = get_active_commission_plan(session, calculation_date)
    product_codes = {line.product_code for line in commission_input.lines}
    products_by_code = get_products_by_code(session, product_codes | {"BUSINESS_INTERNET"})
    connected_units = connected_units_for_lines(commission_input.lines, products_by_code)
    total_incremental_mrr = money(sum((line.incremental_mrr for line in commission_input.lines), ZERO))
    threshold_reached = commission_input.internet_connects >= plan.minimum_internet_threshold
    tier = get_tier_for_internet_count(plan, commission_input.internet_connects) if threshold_reached else None

    if threshold_reached and tier is None:
        raise ValueError(f"No commission tier found for {commission_input.internet_connects} Internet connects.")

    first_payable_tier = get_next_tier(plan, plan.minimum_internet_threshold - 1)
    if first_payable_tier is None:
        raise ValueError("Commission plan has no payable tiers.")

    tiered_components: tuple[CommissionComponent, ...] = ()
    a_la_carte_components: tuple[CommissionComponent, ...] = ()
    mrr_percentage = ZERO
    mrr_payout = ZERO
    tiered_earnings = ZERO
    a_la_carte_earnings = ZERO
    bonus_base = ZERO
    bonus_payout = ZERO
    estimated_payout = ZERO

    if tier is not None:
        (
            tiered_components,
            a_la_carte_components,
            total_incremental_mrr,
            mrr_payout,
            tiered_earnings,
            a_la_carte_earnings,
            bonus_base,
            bonus_payout,
            estimated_payout,
        ) = payout_for_tier(commission_input.lines, products_by_code, plan, tier)
        mrr_percentage = money(tier.mrr_percentage)

    internet_needed_for_threshold = max(plan.minimum_internet_threshold - commission_input.internet_connects, 0)
    locked_lines = adjusted_lines_for_internet_target(
        commission_input.lines,
        products_by_code,
        internet_needed_for_threshold,
    )
    locked_payout = payout_for_tier(locked_lines, products_by_code, plan, first_payable_tier)[-1]
    if threshold_reached:
        locked_payout = estimated_payout

    next_tier = get_next_tier(plan, commission_input.internet_connects)
    projected_next_tier_payout: Optional[Decimal] = None
    increase_if_next_tier_reached: Optional[Decimal] = None
    internet_needed_for_next_tier: Optional[int] = None
    if next_tier is not None:
        internet_needed_for_next_tier = next_tier.minimum_internet - commission_input.internet_connects
        projected_lines = adjusted_lines_for_internet_target(
            commission_input.lines,
            products_by_code,
            internet_needed_for_next_tier,
        )
        projected_next_tier_payout = payout_for_tier(projected_lines, products_by_code, plan, next_tier)[-1]
        increase_if_next_tier_reached = money(projected_next_tier_payout - estimated_payout)

    bonus_eligible = connected_units >= plan.bonus_unit_threshold

    return CommissionResult(
        commission_plan_name=plan.name,
        tier_name=tier.tier_name if tier else None,
        threshold_reached=threshold_reached,
        internet_connects=commission_input.internet_connects,
        connected_units=connected_units,
        bonus_eligible=bonus_eligible,
        tiered_components=tiered_components,
        a_la_carte_components=a_la_carte_components,
        total_incremental_mrr=total_incremental_mrr,
        mrr_percentage=mrr_percentage,
        mrr_payout=mrr_payout,
        tiered_earnings=tiered_earnings,
        a_la_carte_earnings=a_la_carte_earnings,
        bonus_base=bonus_base,
        bonus_percentage=money(plan.bonus_percentage),
        bonus_payout=bonus_payout,
        ramp_amount=ZERO,
        estimated_payout=estimated_payout,
        locked_payout=locked_payout,
        next_tier_name=next_tier.tier_name if next_tier else None,
        internet_needed_for_next_tier=internet_needed_for_next_tier,
        projected_next_tier_payout=projected_next_tier_payout,
        increase_if_next_tier_reached=increase_if_next_tier_reached,
    )


def print_demo_result(result: CommissionResult) -> None:
    print(f"Plan: {result.commission_plan_name}")
    print(f"Tier: {result.tier_name}")
    print(f"Connected units: {result.connected_units}")
    print(f"Bonus eligible: {result.bonus_eligible}")
    print(f"Tiered earnings: ${result.tiered_earnings}")
    print(f"A-La-Carte earnings: ${result.a_la_carte_earnings}")
    print(f"MRR payout: ${result.mrr_payout}")
    print(f"Bonus payout: ${result.bonus_payout}")
    print(f"Estimated payout: ${result.estimated_payout}")
    print(f"Next tier: {result.next_tier_name}")
    print(f"Internet needed: {result.internet_needed_for_next_tier}")
    print(f"Projected next-tier payout: ${result.projected_next_tier_payout}")
    print(f"Increase if next tier is reached: ${result.increase_if_next_tier_reached}")


if __name__ == "__main__":
    demo_input = CommissionInput(
        internet_connects=9,
        lines=(
            CommissionLineInput("BUSINESS_INTERNET", 9, Decimal("0.00")),
            CommissionLineInput("BUSINESS_MOBILE", 20, Decimal("0.00")),
            CommissionLineInput("BUSINESS_VOICE", 5, Decimal("0.00")),
            CommissionLineInput("BUSINESS_VIDEO", 2, Decimal("2000.00")),
        ),
    )
    with SessionLocal() as session:
        print_demo_result(calculate_commission(session, demo_input, date.today()))
