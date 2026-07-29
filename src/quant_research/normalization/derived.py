import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.models import (
    NormalizedFinancial,
    NormalizedFinancialDependency,
)


@dataclass(frozen=True)
class DerivedSource:
    """One normalized-financial input to a derived metric."""

    financial: NormalizedFinancial
    coefficient: Decimal | None
    role: str


@dataclass(frozen=True)
class DerivedObservation:
    """One point-in-time observation derived from normalized metrics."""

    metric: str
    value: Decimal
    unit: str
    fiscal_year: int
    fiscal_quarter: int
    period_start: date | None
    period_end: date
    available_at: date
    derivation_type: str
    sources: tuple[DerivedSource, ...]


def create_derived_source_key(
    company_id: int,
    observation: DerivedObservation,
) -> str:
    """Create a deterministic identifier for a derived observation."""

    source_identity = sorted(
        (
            source.financial.source_key,
            (
                str(source.coefficient)
                if source.coefficient is not None
                else None
            ),
            source.role,
        )
        for source in observation.sources
    )

    identity = {
        "company_id": company_id,
        "metric": observation.metric,
        "value": str(
            observation.value.normalize()
        ),
        "unit": observation.unit,
        "period_type": "quarter",
        "fiscal_year": observation.fiscal_year,
        "fiscal_quarter": observation.fiscal_quarter,
        "period_start": (
            observation.period_start.isoformat()
            if observation.period_start is not None
            else None
        ),
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


def store_derived_observation(
    session: Session,
    company_id: int,
    observation: DerivedObservation,
) -> bool:
    """Persist a derived metric and its normalized dependencies."""

    source_key = create_derived_source_key(
        company_id=company_id,
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
        metric=observation.metric,
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

    for source in observation.sources:
        session.add(
            NormalizedFinancialDependency(
                derived_financial_id=normalized.id,
                source_financial_id=source.financial.id,
                coefficient=source.coefficient,
                role=source.role,
            )
        )

    return True
