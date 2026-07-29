from sqlalchemy.orm import Session

from quant_research.database.models import Company
from quant_research.normalization.flow import (
    FlowMetricConfig,
    normalize_cumulative_ytd_metric,
)

CFO_CONFIG = FlowMetricConfig(
    metric="cfo",
    concept_priority={
        "NetCashProvidedByUsedInOperatingActivities": 0,
    },
)


def normalize_cfo(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Normalize quarterly operating cash flow."""

    return normalize_cumulative_ytd_metric(
        session=session,
        company_id=company.id,
        config=CFO_CONFIG,
    )