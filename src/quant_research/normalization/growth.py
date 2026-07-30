from collections import defaultdict
from dataclasses import dataclass
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

GROWTH_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class GrowthMetricConfig:
    """Configuration for one point-in-time YoY growth metric."""

    metric: str
    source_metric: str
    derivation_type: str


REVENUE_YOY_CONFIG = GrowthMetricConfig(
    metric="revenue_yoy",
    source_metric="revenue",
    derivation_type="current_divided_by_prior_year_minus_one",
)


CAPEX_YOY_CONFIG = GrowthMetricConfig(
    metric="capex_yoy",
    source_metric="capex",
    derivation_type="current_divided_by_prior_year_minus_one",
)


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
    """Group observations by fiscal year and fiscal quarter."""

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
    """Return the newest observation available at a given date."""

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


def validate_resolved_period(
    resolver: FiscalPeriodResolver,
    observation: NormalizedFinancial,
    expected_year: int,
    expected_quarter: int,
) -> None:
    """Verify that an observation matches the fiscal calendar."""

    fiscal_period = resolver.try_resolve_by_end(
        observation.period_end
    )

    if fiscal_period is None:
        raise ValueError(
            "Unable to resolve fiscal period for "
            f"normalized_financial_id={observation.id}, "
            f"period_end={observation.period_end}."
        )

    if (
        fiscal_period.fiscal_year != expected_year
        or fiscal_period.fiscal_quarter != expected_quarter
    ):
        raise ValueError(
            "Resolved fiscal period does not match stored fiscal metadata "
            f"for normalized_financial_id={observation.id}."
        )


def build_yoy_growth_observations(
    source_observations: list[NormalizedFinancial],
    config: GrowthMetricConfig,
    resolver: FiscalPeriodResolver,
) -> list[DerivedObservation]:
    """Build point-in-time YoY growth observations."""

    observations_by_period = group_by_fiscal_period(
        source_observations
    )

    derived: list[DerivedObservation] = []

    for (
        fiscal_year,
        fiscal_quarter,
    ) in sorted(observations_by_period):
        current_key = (
            fiscal_year,
            fiscal_quarter,
        )

        prior_key = (
            fiscal_year - 1,
            fiscal_quarter,
        )

        if prior_key not in observations_by_period:
            continue

        current_versions = observations_by_period[
            current_key
        ]

        prior_versions = observations_by_period[
            prior_key
        ]

        event_dates = sorted(
            {
                observation.available_at
                for observation in (
                    current_versions
                    + prior_versions
                )
            }
        )

        previous_sources: tuple[str, str] | None = None

        for event_date in event_dates:
            current = latest_available(
                current_versions,
                event_date,
            )

            prior = latest_available(
                prior_versions,
                event_date,
            )

            if current is None or prior is None:
                continue

            if current.unit != prior.unit:
                raise ValueError(
                    "YoY inputs have different units for "
                    f"{config.metric}, FY{fiscal_year} "
                    f"Q{fiscal_quarter}: "
                    f"{current.unit} and {prior.unit}."
                )

            validate_resolved_period(
                resolver=resolver,
                observation=current,
                expected_year=fiscal_year,
                expected_quarter=fiscal_quarter,
            )

            validate_resolved_period(
                resolver=resolver,
                observation=prior,
                expected_year=fiscal_year - 1,
                expected_quarter=fiscal_quarter,
            )

            if prior.value == 0:
                # YoY growth is undefined when the prior-year value is zero.
                continue

            source_pair = (
                current.source_key,
                prior.source_key,
            )

            # No new PIT view exists unless one of the inputs changed.
            if source_pair == previous_sources:
                continue

            previous_sources = source_pair

            current_period = resolver.resolve_by_end(
                current.period_end
            )

            growth_value = (
                current.value
                / prior.value
                - Decimal(1)
            ).quantize(
                GROWTH_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            )

            derived.append(
                DerivedObservation(
                    metric=config.metric,
                    value=growth_value,
                    unit="ratio",
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                    period_start=current_period.period_start,
                    period_end=current_period.period_end,
                    available_at=max(
                        current.available_at,
                        prior.available_at,
                    ),
                    derivation_type=config.derivation_type,
                    sources=(
                        DerivedSource(
                            financial=current,
                            coefficient=None,
                            role="current_period",
                        ),
                        DerivedSource(
                            financial=prior,
                            coefficient=None,
                            role="prior_year_period",
                        ),
                    ),
                )
            )

    return derived


def normalize_yoy_growth_metric(
    session: Session,
    company: Company,
    config: GrowthMetricConfig,
) -> tuple[int, int]:
    """Normalize one point-in-time YoY growth metric."""

    resolver = FiscalPeriodResolver(
        session=session,
        company_id=company.id,
    )

    source_observations = load_metric_observations(
        session=session,
        company_id=company.id,
        metric=config.source_metric,
    )

    observations = build_yoy_growth_observations(
        source_observations=source_observations,
        config=config,
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


def normalize_revenue_yoy(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Normalize quarterly revenue YoY growth."""

    return normalize_yoy_growth_metric(
        session=session,
        company=company,
        config=REVENUE_YOY_CONFIG,
    )


def normalize_capex_yoy(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Normalize quarterly CAPEX YoY growth."""

    return normalize_yoy_growth_metric(
        session=session,
        company=company,
        config=CAPEX_YOY_CONFIG,
    )
