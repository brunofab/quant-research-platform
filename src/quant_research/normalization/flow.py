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
            FinancialFact.company_id
            == company_id,
            FinancialFact.taxonomy
            == config.taxonomy,
            FinancialFact.concept.in_(
                tuple(
                    config.concept_priority
                )
            ),
            FinancialFact.unit
            == config.unit,
            FinancialFact.form.in_(
                PERIODIC_FORMS
            ),
        )
        .order_by(
            FinancialFact.period_end,
            FinancialFact.filed_at,
        )
    )

    return list(
        session.scalars(
            statement
        ).all()
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

        current_priority = (
            concept_priority.get(
                fact.concept,
                999,
            )
        )

        existing_priority = (
            concept_priority.get(
                existing.concept,
                999,
            )
        )

        if (
            current_priority
            < existing_priority
        ):
            selected[key] = fact

    return list(
        selected.values()
    )


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
        "fiscal_year": (
            observation.fiscal_year
        ),
        "fiscal_quarter": (
            observation.fiscal_quarter
        ),
        "period_start": (
            observation.period_start.isoformat()
        ),
        "period_end": (
            observation.period_end.isoformat()
        ),
        "available_at": (
            observation.available_at.isoformat()
        ),
        "derivation_type": (
            observation.derivation_type
        ),
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

    source_key = (
        create_normalized_source_key(
            company_id=company_id,
            metric=metric,
            observation=observation,
        )
    )

    existing = session.scalar(
        select(
            NormalizedFinancial
        ).where(
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
        fiscal_year=(
            observation.fiscal_year
        ),
        fiscal_quarter=(
            observation.fiscal_quarter
        ),
        period_start=(
            observation.period_start
        ),
        period_end=observation.period_end,
        available_at=(
            observation.available_at
        ),
        derivation_type=(
            observation.derivation_type
        ),
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
                normalized_financial_id=(
                    normalized.id
                ),
                financial_fact_id=fact.id,
                coefficient=coefficient,
                role=role,
            )
        )

    return True
