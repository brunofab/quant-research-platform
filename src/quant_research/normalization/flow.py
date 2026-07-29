import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.models import (
    FinancialFact,
    NormalizedFinancial,
    NormalizedFinancialSource,
)
from quant_research.normalization.fiscal_period_resolver import (
    FiscalPeriodResolver,
    ResolvedFiscalPeriod,
)

PERIODIC_FORMS = (
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
)


@dataclass(frozen=True)
class FlowMetricConfig:
    """Configuration for one normalized financial flow metric."""

    metric: str
    concept_priority: dict[str, int]
    taxonomy: str = "us-gaap"
    unit: str = "USD"


@dataclass(frozen=True)
class FlowObservation:
    """One normalized point-in-time quarterly flow observation."""

    value: Decimal
    unit: str
    fiscal_year: int
    fiscal_quarter: int
    period_start: date
    period_end: date
    available_at: date
    derivation_type: str
    sources: tuple[
        tuple[FinancialFact, Decimal, str],
        ...,
    ]


def period_days(
    fact: FinancialFact,
) -> int | None:
    """Return the inclusive number of days covered by a raw fact."""

    if fact.period_start is None:
        return None

    return (
        fact.period_end
        - fact.period_start
    ).days + 1


def is_quarter_duration(
    days: int | None,
) -> bool:
    """Return whether a duration resembles one fiscal quarter."""

    return (
        days is not None
        and 80 <= days <= 100
    )


def is_six_month_duration(
    days: int | None,
) -> bool:
    """Return whether a duration resembles six months YTD."""

    return (
        days is not None
        and 170 <= days <= 195
    )


def is_nine_month_duration(
    days: int | None,
) -> bool:
    """Return whether a duration resembles nine months YTD."""

    return (
        days is not None
        and 260 <= days <= 285
    )


def is_full_year_duration(
    days: int | None,
) -> bool:
    """Return whether a duration resembles one fiscal year."""

    return (
        days is not None
        and 350 <= days <= 380
    )


def load_flow_facts(
    session: Session,
    company_id: int,
    config: FlowMetricConfig,
) -> list[FinancialFact]:
    """Load candidate SEC facts for one flow metric."""

    statement = (
        select(FinancialFact)
        .where(
            FinancialFact.company_id == company_id,
            FinancialFact.taxonomy == config.taxonomy,
            FinancialFact.concept.in_(
                tuple(config.concept_priority)
            ),
            FinancialFact.unit == config.unit,
            FinancialFact.form.in_(PERIODIC_FORMS),
        )
        .order_by(
            FinancialFact.period_end,
            FinancialFact.filed_at,
        )
    )

    return list(
        session.scalars(statement).all()
    )


def deduplicate_flow_facts(
    facts: list[FinancialFact],
    concept_priority: dict[str, int],
) -> list[FinancialFact]:
    """Choose one preferred concept per SEC reporting context."""

    selected: dict[
        tuple[
            date | None,
            date,
            date,
            str | None,
        ],
        FinancialFact,
    ] = {}

    for fact in facts:
        key = (
            fact.period_start,
            fact.period_end,
            fact.filed_at,
            fact.accession_number,
        )

        existing = selected.get(key)

        if existing is None:
            selected[key] = fact
            continue

        current_priority = concept_priority.get(
            fact.concept,
            999,
        )

        existing_priority = concept_priority.get(
            existing.concept,
            999,
        )

        if current_priority < existing_priority:
            selected[key] = fact

    return list(selected.values())


def create_normalized_source_key(
    company_id: int,
    metric: str,
    observation: FlowObservation,
) -> str:
    """Create a deterministic identifier for a normalized observation."""

    source_identity = sorted(
        (
            fact.source_key,
            str(coefficient),
            role,
        )
        for fact, coefficient, role
        in observation.sources
    )

    identity = {
        "company_id": company_id,
        "metric": metric,
        "value": str(
            observation.value.normalize()
        ),
        "unit": observation.unit,
        "period_type": "quarter",
        "fiscal_year": observation.fiscal_year,
        "fiscal_quarter": observation.fiscal_quarter,
        "period_start": observation.period_start.isoformat(),
        "period_end": observation.period_end.isoformat(),
        "available_at": observation.available_at.isoformat(),
        "derivation_type": observation.derivation_type,
        "sources": source_identity,
    }

    canonical_json = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()


def store_flow_observation(
    session: Session,
    company_id: int,
    metric: str,
    observation: FlowObservation,
) -> bool:
    """Persist one normalized observation and its raw-fact lineage."""

    source_key = create_normalized_source_key(
        company_id=company_id,
        metric=metric,
        observation=observation,
    )

    existing = session.scalar(
        select(NormalizedFinancial).where(
            NormalizedFinancial.source_key
            == source_key
        )
    )

    if existing is not None:
        return False

    normalized = NormalizedFinancial(
        source_key=source_key,
        company_id=company_id,
        metric=metric,
        value=observation.value,
        unit=observation.unit,
        period_type="quarter",
        fiscal_year=observation.fiscal_year,
        fiscal_quarter=observation.fiscal_quarter,
        period_start=observation.period_start,
        period_end=observation.period_end,
        available_at=observation.available_at,
        derivation_type=observation.derivation_type,
    )

    session.add(normalized)

    # We need the generated normalized_financials.id
    # before inserting the lineage rows.
    session.flush()

    for (
        fact,
        coefficient,
        role,
    ) in observation.sources:
        session.add(
            NormalizedFinancialSource(
                normalized_financial_id=normalized.id,
                financial_fact_id=fact.id,
                coefficient=coefficient,
                role=role,
            )
        )

    return True


def matches_cumulative_duration(
    fact: FinancialFact,
    fiscal_quarter: int,
) -> bool:
    """Check whether a raw fact has the expected cumulative YTD duration."""

    days = period_days(fact)

    duration_checks = {
        1: is_quarter_duration,
        2: is_six_month_duration,
        3: is_nine_month_duration,
        4: is_full_year_duration,
    }

    check = duration_checks.get(
        fiscal_quarter
    )

    if check is None:
        return False

    return check(days)


def build_cumulative_ytd_observations(
    facts: list[FinancialFact],
    resolver: FiscalPeriodResolver,
) -> list[FlowObservation]:
    """Convert cumulative YTD facts into standalone quarterly observations."""

    resolved_facts: list[
        tuple[
            FinancialFact,
            ResolvedFiscalPeriod,
        ]
    ] = []

    for fact in facts:
        fiscal_period = (
            resolver.try_resolve_by_end(
                fact.period_end
            )
        )

        if fiscal_period is None:
            continue

        if not matches_cumulative_duration(
            fact,
            fiscal_period.fiscal_quarter,
        ):
            continue

        resolved_facts.append(
            (
                fact,
                fiscal_period,
            )
        )

    observations: list[
        FlowObservation
    ] = []

    for (
        current_fact,
        current_period,
    ) in resolved_facts:
        fiscal_year = (
            current_period.fiscal_year
        )
        fiscal_quarter = (
            current_period.fiscal_quarter
        )

        quarter_start = (
            current_period.period_start
        )

        if quarter_start is None:
            continue

        # Q1 cumulative YTD is already a standalone quarter.
        if fiscal_quarter == 1:
            observations.append(
                FlowObservation(
                    value=current_fact.value,
                    unit=current_fact.unit,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=1,
                    period_start=quarter_start,
                    period_end=current_fact.period_end,
                    available_at=current_fact.filed_at,
                    derivation_type="direct",
                    sources=(
                        (
                            current_fact,
                            Decimal(1),
                            "direct",
                        ),
                    ),
                )
            )

            continue

        prior_quarter = (
            fiscal_quarter - 1
        )

        prior_candidates = [
            fact
            for fact, period
            in resolved_facts
            if (
                period.fiscal_year
                == fiscal_year
                and period.fiscal_quarter
                == prior_quarter
                and fact.filed_at
                <= current_fact.filed_at
            )
        ]

        if not prior_candidates:
            continue

        # Use the newest previous cumulative value
        # that was available when the current fact was filed.
        prior_fact = max(
            prior_candidates,
            key=lambda fact: (
                fact.filed_at,
                fact.accession_number or "",
                fact.id,
            ),
        )

        observations.append(
            FlowObservation(
                value=(
                    current_fact.value
                    - prior_fact.value
                ),
                unit=current_fact.unit,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                period_start=quarter_start,
                period_end=current_fact.period_end,
                available_at=max(
                    current_fact.filed_at,
                    prior_fact.filed_at,
                ),
                derivation_type="ytd_difference",
                sources=(
                    (
                        current_fact,
                        Decimal(1),
                        "ytd_current",
                    ),
                    (
                        prior_fact,
                        Decimal(-1),
                        "ytd_prior",
                    ),
                ),
            )
        )

    return observations


def normalize_cumulative_ytd_metric(
    session: Session,
    company_id: int,
    config: FlowMetricConfig,
) -> tuple[int, int]:
    """Normalize a cumulative-YTD SEC flow metric into quarters."""

    resolver = FiscalPeriodResolver(
        session=session,
        company_id=company_id,
    )

    raw_facts = load_flow_facts(
        session=session,
        company_id=company_id,
        config=config,
    )

    facts = deduplicate_flow_facts(
        facts=raw_facts,
        concept_priority=config.concept_priority,
    )

    observations = (
        build_cumulative_ytd_observations(
            facts=facts,
            resolver=resolver,
        )
    )

    inserted = 0
    skipped = 0

    for observation in observations:
        was_inserted = (
            store_flow_observation(
                session=session,
                company_id=company_id,
                metric=config.metric,
                observation=observation,
            )
        )

        if was_inserted:
            inserted += 1
        else:
            skipped += 1

    return inserted, skipped
