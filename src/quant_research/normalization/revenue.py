from decimal import Decimal

from sqlalchemy.orm import Session

from quant_research.database.models import (
    Company,
    FinancialFact,
)
from quant_research.normalization.fiscal_period_resolver import (
    FiscalPeriodResolver,
)
from quant_research.normalization.flow import (
    FlowMetricConfig,
    FlowObservation,
    deduplicate_flow_facts,
    is_full_year_duration,
    is_nine_month_duration,
    is_quarter_duration,
    load_flow_facts,
    period_days,
    store_flow_observation,
)

REVENUE_CONFIG = FlowMetricConfig(
    metric="revenue",
    concept_priority={
        "Revenues": 0,
        "RevenueFromContractWithCustomerExcludingAssessedTax": 1,
    },
)


def build_direct_quarter_observations(
    facts: list[FinancialFact],
    resolver: FiscalPeriodResolver,
) -> list[FlowObservation]:
    """Build direct quarterly revenue observations."""

    observations: list[
        FlowObservation
    ] = []

    for fact in facts:
        if not is_quarter_duration(
            period_days(fact)
        ):
            continue

        if fact.period_start is None:
            continue

        fiscal_period = (
            resolver.try_resolve_by_end(
                fact.period_end
            )
        )

        if fiscal_period is None:
            continue

        # Q4 revenue is derived from FY - 9M.
        if (
            fiscal_period.fiscal_quarter
            == 4
        ):
            continue

        observations.append(
            FlowObservation(
                value=fact.value,
                unit=fact.unit,
                fiscal_year=(
                    fiscal_period.fiscal_year
                ),
                fiscal_quarter=(
                    fiscal_period.fiscal_quarter
                ),
                period_start=(
                    fact.period_start
                ),
                period_end=fact.period_end,
                available_at=fact.filed_at,
                derivation_type="direct",
                sources=(
                    (
                        fact,
                        Decimal(1),
                        "direct",
                    ),
                ),
            )
        )

    return observations


def build_q4_observations(
    facts: list[FinancialFact],
    resolver: FiscalPeriodResolver,
) -> list[FlowObservation]:
    """Derive Q4 revenue as full-year revenue minus nine-month revenue."""

    annual_facts = [
        fact
        for fact in facts
        if is_full_year_duration(
            period_days(fact)
        )
    ]

    nine_month_facts = [
        fact
        for fact in facts
        if is_nine_month_duration(
            period_days(fact)
        )
    ]

    observations: list[
        FlowObservation
    ] = []

    for annual_fact in annual_facts:
        if (
            annual_fact.period_start
            is None
        ):
            continue

        fiscal_period = (
            resolver.try_resolve_by_end(
                annual_fact.period_end
            )
        )

        if fiscal_period is None:
            continue

        if (
            fiscal_period.fiscal_quarter
            != 4
        ):
            continue

        fiscal_year = (
            fiscal_period.fiscal_year
        )

        candidates: list[
            FinancialFact
        ] = []

        for fact in nine_month_facts:
            candidate_period = (
                resolver.try_resolve_by_end(
                    fact.period_end
                )
            )

            if candidate_period is None:
                continue

            if (
                candidate_period.fiscal_year
                == fiscal_year
                and candidate_period.fiscal_quarter
                == 3
                and fact.filed_at
                <= annual_fact.filed_at
            ):
                candidates.append(fact)

        if not candidates:
            continue

        nine_month_fact = max(
            candidates,
            key=lambda fact: fact.filed_at,
        )

        value = (
            annual_fact.value
            - nine_month_fact.value
        )

        quarter_start = (
            fiscal_period.period_start
        )

        if quarter_start is None:
            continue

        observations.append(
            FlowObservation(
                value=value,
                unit=annual_fact.unit,
                fiscal_year=fiscal_year,
                fiscal_quarter=4,
                period_start=quarter_start,
                period_end=(
                    annual_fact.period_end
                ),
                available_at=max(
                    annual_fact.filed_at,
                    nine_month_fact.filed_at,
                ),
                derivation_type="fy_minus_9m",
                sources=(
                    (
                        annual_fact,
                        Decimal(1),
                        "full_year",
                    ),
                    (
                        nine_month_fact,
                        Decimal(-1),
                        "nine_month_ytd",
                    ),
                ),
            )
        )

    return observations


def normalize_revenue(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Normalize quarterly revenue for one company."""

    resolver = FiscalPeriodResolver(
        session=session,
        company_id=company.id,
    )

    raw_facts = load_flow_facts(
        session=session,
        company_id=company.id,
        config=REVENUE_CONFIG,
    )

    facts = deduplicate_flow_facts(
        facts=raw_facts,
        concept_priority=(
            REVENUE_CONFIG.concept_priority
        ),
    )

    observations = (
        build_direct_quarter_observations(
            facts,
            resolver,
        )
        + build_q4_observations(
            facts,
            resolver,
        )
    )

    inserted = 0
    skipped = 0

    for observation in observations:
        was_inserted = (
            store_flow_observation(
                session=session,
                company_id=company.id,
                metric=REVENUE_CONFIG.metric,
                observation=observation,
            )
        )

        if was_inserted:
            inserted += 1
        else:
            skipped += 1

    return inserted, skipped