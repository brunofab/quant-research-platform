from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.models import (
    Company,
    NormalizedFinancial,
)
from quant_research.normalization.derived import (
    DerivedObservation,
    DerivedSource,
    store_derived_observation,
)


def load_metric_observations(
    session: Session,
    company_id: int,
    metric: str,
) -> list[NormalizedFinancial]:
    """Load quarterly normalized observations for one metric."""

    statement = (
        select(NormalizedFinancial)
        .where(
            NormalizedFinancial.company_id
            == company_id,
            NormalizedFinancial.metric
            == metric,
            NormalizedFinancial.period_type
            == "quarter",
        )
        .order_by(
            NormalizedFinancial.fiscal_year,
            NormalizedFinancial.fiscal_quarter,
            NormalizedFinancial.available_at,
            NormalizedFinancial.source_key,
        )
    )

    return list(
        session.scalars(statement).all()
    )


def latest_available(
    observations: list[NormalizedFinancial],
    available_at,
) -> NormalizedFinancial | None:
    """Return the latest version available at a given date."""

    candidates = [
        observation
        for observation in observations
        if observation.available_at <= available_at
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda observation: (
            observation.available_at,
            observation.source_key,
        ),
    )


def build_fcf_observations(
    cfo_observations: list[NormalizedFinancial],
    capex_observations: list[NormalizedFinancial],
) -> list[DerivedObservation]:
    """Build point-in-time FCF as CFO minus CAPEX."""

    cfo_by_period = defaultdict(list)
    capex_by_period = defaultdict(list)

    for observation in cfo_observations:
        key = (
            observation.fiscal_year,
            observation.fiscal_quarter,
        )
        cfo_by_period[key].append(observation)

    for observation in capex_observations:
        key = (
            observation.fiscal_year,
            observation.fiscal_quarter,
        )
        capex_by_period[key].append(observation)

    common_periods = (
        set(cfo_by_period)
        & set(capex_by_period)
    )

    derived: list[DerivedObservation] = []

    for fiscal_year, fiscal_quarter in sorted(
        common_periods
    ):
        cfo_versions = cfo_by_period[
            (fiscal_year, fiscal_quarter)
        ]
        capex_versions = capex_by_period[
            (fiscal_year, fiscal_quarter)
        ]

        event_dates = sorted(
            {
                observation.available_at
                for observation in (
                    cfo_versions
                    + capex_versions
                )
            }
        )

        previous_sources: tuple[str, str] | None = None

        for event_date in event_dates:
            cfo = latest_available(
                cfo_versions,
                event_date,
            )

            capex = latest_available(
                capex_versions,
                event_date,
            )

            if cfo is None or capex is None:
                continue

            if cfo.unit != capex.unit:
                raise ValueError(
                    "CFO and CAPEX units do not match for "
                    f"FY{fiscal_year} Q{fiscal_quarter}."
                )

            if (
                cfo.period_end
                != capex.period_end
            ):
                raise ValueError(
                    "CFO and CAPEX period_end values do not match for "
                    f"FY{fiscal_year} Q{fiscal_quarter}."
                )

            if (
                cfo.period_start
                != capex.period_start
            ):
                raise ValueError(
                    "CFO and CAPEX period_start values do not match for "
                    f"FY{fiscal_year} Q{fiscal_quarter}."
                )

            source_pair = (
                cfo.source_key,
                capex.source_key,
            )

            # If neither input changed, this event creates no new FCF view.
            if source_pair == previous_sources:
                continue

            previous_sources = source_pair

            derived.append(
                DerivedObservation(
                    metric="fcf",
                    value=(
                        cfo.value
                        - capex.value
                    ),
                    unit=cfo.unit,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                    period_start=cfo.period_start,
                    period_end=cfo.period_end,
                    available_at=max(
                        cfo.available_at,
                        capex.available_at,
                    ),
                    derivation_type="cfo_minus_capex",
                    sources=(
                        DerivedSource(
                            financial=cfo,
                            coefficient=Decimal(1),
                            role="cfo",
                        ),
                        DerivedSource(
                            financial=capex,
                            coefficient=Decimal(-1),
                            role="capex",
                        ),
                    ),
                )
            )

    return derived


def normalize_fcf(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Normalize point-in-time quarterly free cash flow."""

    cfo_observations = load_metric_observations(
        session=session,
        company_id=company.id,
        metric="cfo",
    )

    capex_observations = load_metric_observations(
        session=session,
        company_id=company.id,
        metric="capex",
    )

    observations = build_fcf_observations(
        cfo_observations=cfo_observations,
        capex_observations=capex_observations,
    )

    inserted = 0
    skipped = 0

    for observation in observations:
        was_inserted = store_derived_observation(
            session=session,
            company_id=company.id,
            observation=observation,
        )

        if was_inserted:
            inserted += 1
        else:
            skipped += 1

    return inserted, skipped
