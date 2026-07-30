from sqlalchemy.orm import Session

from quant_research.database.models import Company
from quant_research.normalization.flow import (
    FlowMetricConfig,
    normalize_cumulative_ytd_metric,
)

CAPEX_CONFIG = FlowMetricConfig(
    metric="capex",
    concept_priority={
        # Preferred standard US-GAAP concept.
        "PaymentsToAcquirePropertyPlantAndEquipment": 0,

        # Used by Amazon for current gross cash CAPEX.
        "PaymentsToAcquireProductiveAssets": 1,
    },
)


def normalize_capex(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Normalize quarterly gross cash capital expenditures."""

    return normalize_cumulative_ytd_metric(
        session=session,
        company_id=company.id,
        config=CAPEX_CONFIG,
    )