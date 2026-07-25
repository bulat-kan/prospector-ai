from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.commission import (
    CommissionInput,
    CommissionLineInput,
    calculate_commission,
    get_active_commission_plan,
    get_next_tier,
    get_tier_for_internet_count,
)
from app.models import CommissionPlan, Product
from app.seed_demo import COMMISSION_PLAN_NAME, seed_configuration


def line(product_code: str, quantity: int, mrr: str = "0.00") -> CommissionLineInput:
    return CommissionLineInput(product_code, quantity, Decimal(mrr))


@pytest.fixture
def seeded_session(db_session):
    seed_configuration(db_session)
    return db_session


def test_active_plan_lookup(seeded_session) -> None:
    plan = get_active_commission_plan(seeded_session, date(2026, 7, 1))

    assert plan.name == COMMISSION_PLAN_NAME


def test_no_active_plan_raises_error(seeded_session) -> None:
    with pytest.raises(ValueError, match="No active commission plan"):
        get_active_commission_plan(seeded_session, date(2025, 12, 31))


def test_overlapping_active_plans_raise_error(seeded_session) -> None:
    seeded_session.add(
        CommissionPlan(
            name="Overlapping Plan",
            effective_start=date(2026, 1, 1),
            active=True,
            bonus_percentage=Decimal("0.00"),
            bonus_unit_threshold=0,
            minimum_internet_threshold=0,
        )
    )
    seeded_session.commit()

    with pytest.raises(ValueError, match="Multiple active commission plans"):
        get_active_commission_plan(seeded_session, date(2026, 7, 1))


@pytest.mark.parametrize(
    ("internet_count", "tier_name"),
    [
        (5, "5-9"),
        (9, "5-9"),
        (10, "10-14"),
        (14, "10-14"),
        (15, "15-19"),
        (19, "15-19"),
        (20, "20-24"),
        (24, "20-24"),
        (25, "25-29"),
        (29, "25-29"),
        (30, "30+"),
    ],
)
def test_tier_boundaries(seeded_session, internet_count: int, tier_name: str) -> None:
    plan = get_active_commission_plan(seeded_session, date(2026, 7, 1))
    tier = get_tier_for_internet_count(plan, internet_count)

    assert tier is not None
    assert tier.tier_name == tier_name


def test_below_threshold_lock(seeded_session) -> None:
    result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=4,
            lines=(
                line("BUSINESS_INTERNET", 4),
                line("BUSINESS_MOBILE", 10),
                line("BUSINESS_VOICE", 2),
                line("BUSINESS_VIDEO", 1, "1000.00"),
            ),
        ),
        date(2026, 7, 1),
    )

    assert result.estimated_payout == Decimal("0.00")
    assert result.locked_payout == Decimal("1720.00")
    assert result.next_tier_name == "5-9"
    assert result.internet_needed_for_next_tier == 1


def test_five_internet_example(seeded_session) -> None:
    result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=5,
            lines=(
                line("BUSINESS_INTERNET", 5),
                line("BUSINESS_MOBILE", 5),
                line("BUSINESS_VOICE", 5),
                line("BUSINESS_VIDEO", 5, "1000.00"),
            ),
        ),
        date(2026, 7, 1),
    )

    payouts = {component.product_code: component.payout for component in result.tiered_components}
    assert result.connected_units == 20
    assert result.bonus_eligible is True
    assert result.tiered_earnings == Decimal("1425.00")
    assert payouts["BUSINESS_INTERNET"] == Decimal("500.00")
    assert payouts["BUSINESS_MOBILE"] == Decimal("375.00")
    assert payouts["BUSINESS_VOICE"] == Decimal("300.00")
    assert payouts["BUSINESS_VIDEO"] == Decimal("250.00")
    assert result.mrr_payout == Decimal("300.00")
    assert result.bonus_base == Decimal("1425.00")
    assert result.bonus_payout == Decimal("106.88")
    assert result.estimated_payout == Decimal("1831.88")


def test_a_la_carte_example(seeded_session) -> None:
    result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=5,
            lines=(
                line("BUSINESS_INTERNET", 5),
                line("WIB", 2),
                line("INVINCIBLE_WIFI", 1),
                line("UNLIMITED_PLUS", 3),
            ),
        ),
        date(2026, 7, 1),
    )

    assert result.a_la_carte_earnings == Decimal("450.00")


def test_bonus_with_a_la_carte_excludes_mrr(seeded_session) -> None:
    result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=5,
            lines=(
                line("BUSINESS_INTERNET", 5),
                line("BUSINESS_MOBILE", 15, "1000.00"),
                line("WIB", 2),
            ),
        ),
        date(2026, 7, 1),
    )

    assert result.connected_units == 20
    assert result.tiered_earnings == Decimal("1625.00")
    assert result.a_la_carte_earnings == Decimal("200.00")
    assert result.mrr_payout == Decimal("300.00")
    assert result.bonus_base == Decimal("1825.00")
    assert result.bonus_payout == Decimal("136.88")


def test_no_bonus_at_19_connected_units(seeded_session) -> None:
    result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=5,
            lines=(line("BUSINESS_INTERNET", 5), line("BUSINESS_MOBILE", 14)),
        ),
        date(2026, 7, 1),
    )

    assert result.connected_units == 19
    assert result.bonus_eligible is False
    assert result.bonus_payout == Decimal("0.00")


def test_bonus_at_exactly_20_connected_units(seeded_session) -> None:
    result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=5,
            lines=(line("BUSINESS_INTERNET", 5), line("BUSINESS_MOBILE", 15)),
        ),
        date(2026, 7, 1),
    )

    assert result.connected_units == 20
    assert result.bonus_eligible is True
    assert result.bonus_payout > Decimal("0.00")


def test_mrr_examples(seeded_session) -> None:
    new_customer = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=5,
            lines=(line("BUSINESS_INTERNET", 5, "170.00"),),
        ),
        date(2026, 7, 1),
    )
    existing_customer = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=5,
            lines=(line("BUSINESS_INTERNET", 5), line("BUSINESS_MOBILE", 1, "100.00")),
        ),
        date(2026, 7, 1),
    )

    assert new_customer.mrr_payout == Decimal("51.00")
    assert existing_customer.mrr_payout == Decimal("30.00")


def test_next_tier_projection_from_9_to_10_internet(seeded_session) -> None:
    result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=9,
            lines=(
                line("BUSINESS_INTERNET", 9),
                line("BUSINESS_MOBILE", 20),
                line("BUSINESS_VOICE", 5),
                line("BUSINESS_VIDEO", 2, "2000.00"),
            ),
        ),
        date(2026, 7, 1),
    )

    assert result.tier_name == "5-9"
    assert result.next_tier_name == "10-14"
    assert result.internet_needed_for_next_tier == 1
    assert result.estimated_payout == Decimal("3610.00")
    assert result.projected_next_tier_payout == Decimal("7435.00")
    assert result.increase_if_next_tier_reached == Decimal("3825.00")


def test_highest_tier_has_no_next_tier_projection(seeded_session) -> None:
    result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=30,
            lines=(line("BUSINESS_INTERNET", 30),),
        ),
        date(2026, 7, 1),
    )

    assert result.tier_name == "30+"
    assert result.next_tier_name is None
    assert result.internet_needed_for_next_tier is None
    assert result.projected_next_tier_payout is None
    assert result.increase_if_next_tier_reached is None


def test_negative_values_raise_errors(seeded_session) -> None:
    with pytest.raises(ValueError, match="Quantity cannot be negative"):
        calculate_commission(
            seeded_session,
            CommissionInput(5, (line("BUSINESS_INTERNET", -1),)),
            date(2026, 7, 1),
        )

    with pytest.raises(ValueError, match="Incremental MRR cannot be negative"):
        calculate_commission(
            seeded_session,
            CommissionInput(5, (line("BUSINESS_INTERNET", 1, "-1.00"),)),
            date(2026, 7, 1),
        )

    with pytest.raises(ValueError, match="Internet connects cannot be negative"):
        calculate_commission(
            seeded_session,
            CommissionInput(-1, (line("BUSINESS_INTERNET", 1),)),
            date(2026, 7, 1),
        )


def test_unknown_product_code_raises_error(seeded_session) -> None:
    with pytest.raises(ValueError, match="Unknown or inactive product code"):
        calculate_commission(
            seeded_session,
            CommissionInput(5, (line("NOT_A_PRODUCT", 1),)),
            date(2026, 7, 1),
        )


def test_product_configuration_behavior(seeded_session) -> None:
    result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=5,
            lines=(line("BUSINESS_INTERNET", 5), line("WIB", 2)),
        ),
        date(2026, 7, 1),
    )
    assert result.connected_units == 5
    assert result.a_la_carte_earnings == Decimal("200.00")

    product = seeded_session.scalar(select(Product).where(Product.code == "WIB"))
    assert product is not None
    product.counts_as_connected_unit = True
    product.flat_commission_amount = Decimal("125.00")
    seeded_session.commit()

    updated_result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=5,
            lines=(line("BUSINESS_INTERNET", 5), line("WIB", 2)),
        ),
        date(2026, 7, 1),
    )
    assert updated_result.connected_units == 7
    assert updated_result.a_la_carte_earnings == Decimal("250.00")


def test_decimal_precision(seeded_session) -> None:
    result = calculate_commission(
        seeded_session,
        CommissionInput(
            internet_connects=5,
            lines=(line("BUSINESS_INTERNET", 5, "170.333"), line("UNLIMITED_PLUS", 1)),
        ),
        date(2026, 7, 1),
    )

    amounts = [
        result.total_incremental_mrr,
        result.mrr_percentage,
        result.mrr_payout,
        result.tiered_earnings,
        result.a_la_carte_earnings,
        result.bonus_base,
        result.bonus_percentage,
        result.bonus_payout,
        result.ramp_amount,
        result.estimated_payout,
        result.locked_payout,
    ]
    assert all(amount == amount.quantize(Decimal("0.01")) for amount in amounts)


def test_input_immutability() -> None:
    commission_input = CommissionInput(5, (line("BUSINESS_INTERNET", 5),))

    with pytest.raises(FrozenInstanceError):
        commission_input.internet_connects = 6
    with pytest.raises(FrozenInstanceError):
        commission_input.lines[0].quantity = 6
