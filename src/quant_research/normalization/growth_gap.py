from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

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
from quant_research.normalization.fiscal_period_resolver import (
    FiscalPeriodResolver,
)

GAP_QUANTUM = Decimal("0.000001")


def load_metric_observations(
    session: Session,
    company_id: int,
    metric: str,
) -> list[NormalizedFinancial]:
    """Load quarterly point-in-time versions for one metric."""

    statement = (
        select(NormalizedFinancial)
        .where(
            NormalizedFinancial.company_id == company_id,
            NormalizedFinancial.metric == metric,
            NormalizedFinancial.period_type == "quarter",
            NormalizedFinancial.fiscal_quarter.is_not(None),
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


def group_by_fiscal_period(
    observations: list[NormalizedFinancial],
) -> dict[
    tuple[int, int],
    list[NormalizedFinancial],
]:
    """Group observations by fiscal year and quarter."""

    grouped: dict[
        tuple[int, int],
        list[NormalizedFinancial],
    ] = defaultdict(list)

    for observation in observations:
        fiscal_quarter = observation.fiscal_quarter

        if fiscal_quarter is None:
            raise ValueError(
                "Quarterly observation has no fiscal_quarter: "
                f"normalized_financial_id={observation.id}."
            )

        key = (
            observation.fiscal_year,
            fiscal_quarter,
        )

        grouped[key].append(observation)

    return dict(grouped)


def latest_available(
    observations: list[NormalizedFinancial],
    available_at: date,
) -> NormalizedFinancial | None:
    """Return the newest version available at a given date."""

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


def build_capex_growth_gap_observations(
    capex_yoy_observations: list[NormalizedFinancial],
    revenue_yoy_observations: list[NormalizedFinancial],
    resolver: FiscalPeriodResolver,
) -> list[DerivedObservation]:
    """Build point-in-time CAPEX YoY minus Revenue YoY."""

    capex_by_period = group_by_fiscal_period(
        capex_yoy_observations
    )

    revenue_by_period = group_by_fiscal_period(
        revenue_yoy_observations
    )

    common_periods = (
        set(capex_by_period)
        & set(revenue_by_period)
    )

    derived: list[DerivedObservation] = []

    for fiscal_year, fiscal_quarter in sorted(
        common_periods
    ):
        period_key = (
            fiscal_year,
            fiscal_quarter,
        )

        capex_versions = capex_by_period[
            period_key
        ]

        revenue_versions = revenue_by_period[
            period_key
        ]

        event_dates = sorted(
            {
                observation.available_at
                for observation in (
                    capex_versions
                    + revenue_versions
                )
            }
        )

        previous_sources: tuple[str, str] | None = None

        for event_date in event_dates:
            capex_yoy = latest_available(
                capex_versions,
                event_date,
            )

            revenue_yoy = latest_available(
                revenue_versions,
                event_date,
            )

            if capex_yoy is None or revenue_yoy is None:
                continue

            if capex_yoy.unit != "ratio":
                raise ValueError(
                    "CAPEX YoY must use unit='ratio' for "
                    f"FY{fiscal_year} Q{fiscal_quarter}."
                )

            if revenue_yoy.unit != "ratio":
                raise ValueError(
                    "Revenue YoY must use unit='ratio' for "
                    f"FY{fiscal_year} Q{fiscal_quarter}."
                )

            if capex_yoy.period_end != revenue_yoy.period_end:
                raise ValueError(
                    "Growth-gap inputs have different period_end "
                    f"values for FY{fiscal_year} "
                    f"Q{fiscal_quarter}."
                )

            fiscal_period = resolver.try_resolve_by_end(
                capex_yoy.period_end
            )

            if fiscal_period is None:
                raise ValueError(
                    "Unable to resolve fiscal period for "
                    f"CAPEX growth gap FY{fiscal_year} "
                    f"Q{fiscal_quarter}."
                )

            if (
                fiscal_period.fiscal_year != fiscal_year
                or fiscal_period.fiscal_quarter
                != fiscal_quarter
            ):
                raise ValueError(
                    "Resolved fiscal period does not match "
                    f"CAPEX growth-gap group FY{fiscal_year} "
                    f"Q{fiscal_quarter}."
                )

            source_pair = (
                capex_yoy.source_key,
                revenue_yoy.source_key,
            )

            # No new PIT view unless one of the inputs changed.
            if source_pair == previous_sources:
                continue

            previous_sources = source_pair

            gap_value = (
                capex_yoy.value
                - revenue_yoy.value
            ).quantize(
                GAP_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            )

            derived.append(
                DerivedObservation(
                    metric="capex_growth_gap",
                    value=gap_value,
                    unit="ratio",
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                    period_start=fiscal_period.period_start,
                    period_end=fiscal_period.period_end,
                    available_at=max(
                        capex_yoy.available_at,
                        revenue_yoy.available_at,
                    ),
                    derivation_type=(
                        "capex_yoy_minus_revenue_yoy"
                    ),
                    sources=(
                        DerivedSource(
                            financial=capex_yoy,
                            coefficient=Decimal(1),
                            role="capex_yoy",
                        ),
                        DerivedSource(
                            financial=revenue_yoy,
                            coefficient=Decimal(-1),
                            role="revenue_yoy",
                        ),
                    ),
                )
            )

    return derived


def normalize_capex_growth_gap(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Normalize CAPEX YoY minus Revenue YoY."""

    resolver = FiscalPeriodResolver(
        session=session,
        company_id=company.id,
    )

    capex_yoy_observations = load_metric_observations(
        session=session,
        company_id=company.id,
        metric="capex_yoy",
    )

    revenue_yoy_observations = load_metric_observations(
        session=session,
        company_id=company.id,
        metric="revenue_yoy",
    )

    observations = build_capex_growth_gap_observations(
        capex_yoy_observations=capex_yoy_observations,
        revenue_yoy_observations=revenue_yoy_observations,
        resolver=resolver,
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
