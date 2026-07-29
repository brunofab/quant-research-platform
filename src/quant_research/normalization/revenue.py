import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.models import (
    Company,
    FinancialFact,
    NormalizedFinancial,
    NormalizedFinancialSource,
)
from quant_research.normalization.fiscal_period_resolver import (
    FiscalPeriodResolver,
)

REVENUE_CONCEPT_PRIORITY = {
    "Revenues": 0,
    "RevenueFromContractWithCustomerExcludingAssessedTax": 1,
}

PERIODIC_FORMS = {
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
}


@dataclass(frozen=True)
class RevenueObservation:
    value: Decimal
    unit: str
    fiscal_year: int
    fiscal_quarter: int
    period_start: date
    period_end: date
    available_at: date
    derivation_type: str
    sources: tuple[tuple[FinancialFact, Decimal, str], ...]


def period_days(fact: FinancialFact) -> int | None:
    """Return the inclusive number of days covered by a fact."""

    if fact.period_start is None:
        return None

    return (fact.period_end - fact.period_start).days + 1


def is_quarter_duration(days: int | None) -> bool:
    """Return whether a duration looks like one fiscal quarter."""

    return days is not None and 80 <= days <= 100


def is_nine_month_duration(days: int | None) -> bool:
    """Return whether a duration looks like a nine-month YTD period."""

    return days is not None and 260 <= days <= 285


def is_full_year_duration(days: int | None) -> bool:
    """Return whether a duration looks like a full fiscal year."""

    return days is not None and 350 <= days <= 380


def load_revenue_facts(
    session: Session,
    company_id: int,
) -> list[FinancialFact]:
    """Load candidate raw SEC revenue facts."""

    statement = (
        select(FinancialFact)
        .where(
            FinancialFact.company_id == company_id,
            FinancialFact.taxonomy == "us-gaap",
            FinancialFact.concept.in_(
                REVENUE_CONCEPT_PRIORITY.keys()
            ),
            FinancialFact.unit == "USD",
            FinancialFact.form.in_(PERIODIC_FORMS),
        )
        .order_by(
            FinancialFact.period_end,
            FinancialFact.filed_at,
        )
    )

    return list(session.scalars(statement).all())

def deduplicate_revenue_facts(
    facts: list[FinancialFact],
) -> list[FinancialFact]:
    """Choose one preferred revenue concept per reporting context."""

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

        current_priority = REVENUE_CONCEPT_PRIORITY.get(
            fact.concept,
            999,
        )

        existing_priority = REVENUE_CONCEPT_PRIORITY.get(
            existing.concept,
            999,
        )

        if current_priority < existing_priority:
            selected[key] = fact

    return list(selected.values())

def build_direct_quarter_observations(
    facts: list[FinancialFact],
    resolver: FiscalPeriodResolver,
) -> list[RevenueObservation]:
    """Build direct quarterly revenue observations."""

    observations: list[RevenueObservation] = []

    for fact in facts:
        days = period_days(fact)

        if not is_quarter_duration(days):
            continue

        if fact.period_start is None:
            continue

        fiscal_period = resolver.resolve_by_end(
            fact.period_end
        )

        if fiscal_period.fiscal_quarter == 4:
            continue

        observations.append(
            RevenueObservation(
                value=fact.value,
                unit=fact.unit,
                fiscal_year=fiscal_period.fiscal_year,
                fiscal_quarter=(
                    fiscal_period.fiscal_quarter
                ),
                period_start=fact.period_start,
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
) -> list[RevenueObservation]:
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

    observations: list[RevenueObservation] = []

    for annual_fact in annual_facts:
        if annual_fact.period_start is None:
            continue

        fiscal_period = resolver.resolve_by_end(
            annual_fact.period_end
        )

        if fiscal_period.fiscal_quarter != 4:
            continue

        fiscal_year = fiscal_period.fiscal_year

        candidates = []

        for fact in nine_month_facts:
            try:
                candidate_period = (
                    resolver.resolve_by_end(
                        fact.period_end
                    )
                )
            except ValueError:
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
            RevenueObservation(
                value=value,
                unit=annual_fact.unit,
                fiscal_year=fiscal_year,
                fiscal_quarter=4,
                period_start=quarter_start,
                period_end=annual_fact.period_end,
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

def create_normalized_source_key(
    company_id: int,
    observation: RevenueObservation,
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
        "metric": "revenue",
        "value": str(observation.value.normalize()),
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

def store_observation(
    session: Session,
    company_id: int,
    observation: RevenueObservation,
) -> bool:
    """Persist one normalized observation and its source lineage."""

    source_key = create_normalized_source_key(
        company_id,
        observation,
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
        metric="revenue",
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
    session.flush()

    for fact, coefficient, role in observation.sources:
        session.add(
            NormalizedFinancialSource(
                normalized_financial_id=normalized.id,
                financial_fact_id=fact.id,
                coefficient=coefficient,
                role=role,
            )
        )

    return True

def normalize_revenue(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Normalize quarterly revenue for one company."""

    resolver = FiscalPeriodResolver(
        session=session,
        company_id=company.id,
    )

    raw_facts = load_revenue_facts(
        session,
        company.id,
    )

    facts = deduplicate_revenue_facts(
        raw_facts
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
        if store_observation(
            session,
            company.id,
            observation,
        ):
            inserted += 1
        else:
            skipped += 1

    return inserted, skipped