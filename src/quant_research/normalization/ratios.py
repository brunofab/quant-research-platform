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

RATIO_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class RatioMetricConfig:
    """Configuration for one point-in-time financial ratio."""

    metric: str
    numerator_metric: str
    denominator_metric: str
    derivation_type: str


CAPEX_INTENSITY_CONFIG = RatioMetricConfig(
    metric="capex_intensity",
    numerator_metric="capex",
    denominator_metric="revenue",
    derivation_type="capex_divided_by_revenue",
)


FCF_MARGIN_CONFIG = RatioMetricConfig(
    metric="fcf_margin",
    numerator_metric="fcf",
    denominator_metric="revenue",
    derivation_type="fcf_divided_by_revenue",
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
    """Group normalized observations by fiscal year and quarter."""

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


def build_ratio_observations(
    numerator_observations: list[NormalizedFinancial],
    denominator_observations: list[NormalizedFinancial],
    config: RatioMetricConfig,
    resolver: FiscalPeriodResolver,
) -> list[DerivedObservation]:
    """Build point-in-time versions of one financial ratio."""

    numerator_by_period = group_by_fiscal_period(
        numerator_observations
    )

    denominator_by_period = group_by_fiscal_period(
        denominator_observations
    )

    common_periods = (
        set(numerator_by_period)
        & set(denominator_by_period)
    )

    derived: list[DerivedObservation] = []

    for fiscal_year, fiscal_quarter in sorted(
        common_periods
    ):
        period_key = (
            fiscal_year,
            fiscal_quarter,
        )

        numerator_versions = numerator_by_period[
            period_key
        ]

        denominator_versions = denominator_by_period[
            period_key
        ]

        event_dates = sorted(
            {
                observation.available_at
                for observation in (
                    numerator_versions
                    + denominator_versions
                )
            }
        )

        previous_sources: tuple[str, str] | None = None

        for event_date in event_dates:
            numerator = latest_available(
                numerator_versions,
                event_date,
            )

            denominator = latest_available(
                denominator_versions,
                event_date,
            )

            if numerator is None or denominator is None:
                continue

            if numerator.unit != denominator.unit:
                raise ValueError(
                    "Ratio inputs have different units for "
                    f"{config.metric}, FY{fiscal_year} "
                    f"Q{fiscal_quarter}: "
                    f"{numerator.unit} and {denominator.unit}."
                )

            if numerator.period_end != denominator.period_end:
                raise ValueError(
                    "Ratio inputs have different period_end values for "
                    f"{config.metric}, FY{fiscal_year} "
                    f"Q{fiscal_quarter}: "
                    f"{numerator.period_end} and "
                    f"{denominator.period_end}."
                )

            fiscal_period = resolver.try_resolve_by_end(
                numerator.period_end
            )

            if fiscal_period is None:
                raise ValueError(
                    "Unable to resolve the canonical fiscal period for "
                    f"{config.metric}, FY{fiscal_year} "
                    f"Q{fiscal_quarter}, "
                    f"period_end={numerator.period_end}."
                )

            if (
                fiscal_period.fiscal_year != fiscal_year
                or fiscal_period.fiscal_quarter
                != fiscal_quarter
            ):
                raise ValueError(
                    "Resolved fiscal period does not match the ratio "
                    f"group for {config.metric}, FY{fiscal_year} "
                    f"Q{fiscal_quarter}."
                )

            if denominator.value == 0:
                raise ValueError(
                    "Cannot divide by zero for "
                    f"{config.metric}, FY{fiscal_year} "
                    f"Q{fiscal_quarter}, "
                    f"available_at={event_date}."
                )

            source_pair = (
                numerator.source_key,
                denominator.source_key,
            )

            # If neither selected input changed, no new PIT view exists.
            if source_pair == previous_sources:
                continue

            previous_sources = source_pair

            ratio_value = (
                numerator.value
                / denominator.value
            ).quantize(
                RATIO_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            )

            derived.append(
                DerivedObservation(
                    metric=config.metric,
                    value=ratio_value,
                    unit="ratio",
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                    period_start=fiscal_period.period_start,
                    period_end=fiscal_period.period_end,
                    available_at=max(
                        numerator.available_at,
                        denominator.available_at,
                    ),
                    derivation_type=config.derivation_type,
                    sources=(
                        DerivedSource(
                            financial=numerator,
                            coefficient=None,
                            role="numerator",
                        ),
                        DerivedSource(
                            financial=denominator,
                            coefficient=None,
                            role="denominator",
                        ),
                    ),
                )
            )

    return derived


def normalize_ratio_metric(
    session: Session,
    company: Company,
    config: RatioMetricConfig,
) -> tuple[int, int]:
    """Normalize one point-in-time financial ratio."""

    resolver = FiscalPeriodResolver(
        session=session,
        company_id=company.id,
    )

    numerator_observations = load_metric_observations(
        session=session,
        company_id=company.id,
        metric=config.numerator_metric,
    )

    denominator_observations = load_metric_observations(
        session=session,
        company_id=company.id,
        metric=config.denominator_metric,
    )

    observations = build_ratio_observations(
        numerator_observations=numerator_observations,
        denominator_observations=denominator_observations,
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


def normalize_capex_intensity(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Normalize CAPEX divided by revenue."""

    return normalize_ratio_metric(
        session=session,
        company=company,
        config=CAPEX_INTENSITY_CONFIG,
    )


def normalize_fcf_margin(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Normalize free cash flow divided by revenue."""

    return normalize_ratio_metric(
        session=session,
        company=company,
        config=FCF_MARGIN_CONFIG,
    )
