from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.models import NormalizedFinancial
from quant_research.normalization.fiscal_period_resolver import (
    FiscalPeriodResolver,
)

CAPITAL_CYCLE_FEATURE_METRICS = (
    "capex_growth_gap",
    "capex_intensity_yoy_delta",
    "fcf_margin_yoy_delta",
    "capex_growth_gap_qoq_delta",
    "capex_intensity_yoy_delta_qoq_delta",
    "fcf_margin_yoy_delta_qoq_delta",
)

class SnapshotVintage(str, Enum):
    """Which point-in-time version to select per fiscal period."""

    FIRST = "first"
    LATEST = "latest"


@dataclass(frozen=True)
class CapitalCycleFeatureSnapshot:
    """One complete point-in-time capital-cycle feature snapshot."""

    company_id: int
    fiscal_year: int
    fiscal_quarter: int
    period_start: date | None
    period_end: date
    as_of: date

    capex_growth_gap: Decimal
    capex_intensity_yoy_delta: Decimal
    fcf_margin_yoy_delta: Decimal

    capex_growth_gap_qoq_delta: Decimal
    capex_intensity_yoy_delta_qoq_delta: Decimal
    fcf_margin_yoy_delta_qoq_delta: Decimal

    source_state: tuple[
        tuple[str, str],
        ...,
    ]


def load_capital_cycle_feature_observations(
    session: Session,
    company_id: int,
) -> list[NormalizedFinancial]:
    """Load every point-in-time version of the six feature metrics."""

    statement = (
        select(NormalizedFinancial)
        .where(
            NormalizedFinancial.company_id == company_id,
            NormalizedFinancial.metric.in_(
                CAPITAL_CYCLE_FEATURE_METRICS
            ),
            NormalizedFinancial.period_type == "quarter",
            NormalizedFinancial.fiscal_quarter.is_not(None),
        )
        .order_by(
            NormalizedFinancial.fiscal_year,
            NormalizedFinancial.fiscal_quarter,
            NormalizedFinancial.metric,
            NormalizedFinancial.available_at,
            NormalizedFinancial.source_key,
        )
    )

    return list(
        session.scalars(statement).all()
    )


def group_feature_observations(
    observations: list[NormalizedFinancial],
) -> dict[
    tuple[int, int],
    dict[str, list[NormalizedFinancial]],
]:
    """Group observations by fiscal period and metric."""

    grouped: dict[
        tuple[int, int],
        dict[str, list[NormalizedFinancial]],
    ] = {}

    for observation in observations:
        fiscal_quarter = observation.fiscal_quarter

        if fiscal_quarter is None:
            raise ValueError(
                "Quarterly feature observation has no fiscal_quarter: "
                f"normalized_financial_id={observation.id}."
            )

        period_key = (
            observation.fiscal_year,
            fiscal_quarter,
        )

        metrics_for_period = grouped.setdefault(
            period_key,
            {},
        )

        versions_for_metric = metrics_for_period.setdefault(
            observation.metric,
            [],
        )

        versions_for_metric.append(observation)

    return grouped


def latest_available(
    observations: list[NormalizedFinancial],
    as_of: date,
) -> NormalizedFinancial | None:
    """Return the latest observation available at one historical date."""

    candidates = [
        observation
        for observation in observations
        if observation.available_at <= as_of
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


def build_capital_cycle_feature_snapshots(
    observations: list[NormalizedFinancial],
    resolver: FiscalPeriodResolver,
) -> list[CapitalCycleFeatureSnapshot]:
    """Build complete point-in-time snapshots of all six features."""

    observations_by_period = group_feature_observations(
        observations
    )

    snapshots: list[
        CapitalCycleFeatureSnapshot
    ] = []

    for (
        fiscal_year,
        fiscal_quarter,
    ) in sorted(observations_by_period):
        feature_versions = observations_by_period[
            (
                fiscal_year,
                fiscal_quarter,
            )
        ]

        missing_metrics = [
            metric
            for metric in CAPITAL_CYCLE_FEATURE_METRICS
            if metric not in feature_versions
        ]

        # A snapshot is only useful when all six features exist.
        if missing_metrics:
            continue

        event_dates = sorted(
            {
                observation.available_at
                for metric in CAPITAL_CYCLE_FEATURE_METRICS
                for observation in feature_versions[metric]
            }
        )

        previous_source_state: (
            tuple[tuple[str, str], ...]
            | None
        ) = None

        for event_date in event_dates:
            selected: dict[
                str,
                NormalizedFinancial,
            ] = {}

            for metric in CAPITAL_CYCLE_FEATURE_METRICS:
                observation = latest_available(
                    observations=feature_versions[metric],
                    as_of=event_date,
                )

                if observation is None:
                    break

                selected[metric] = observation

            if len(selected) != len(
                CAPITAL_CYCLE_FEATURE_METRICS
            ):
                continue

            invalid_units = {
                metric: observation.unit
                for metric, observation in selected.items()
                if observation.unit != "ratio"
            }

            if invalid_units:
                raise ValueError(
                    "Capital-cycle features must use unit='ratio': "
                    f"FY{fiscal_year} Q{fiscal_quarter}, "
                    f"invalid={invalid_units}."
                )

            period_ends = {
                observation.period_end
                for observation in selected.values()
            }

            if len(period_ends) != 1:
                raise ValueError(
                    "Capital-cycle features have different period_end "
                    f"values for FY{fiscal_year} Q{fiscal_quarter}: "
                    f"{sorted(period_ends)}."
                )

            period_end = next(iter(period_ends))

            fiscal_period = resolver.try_resolve_by_end(
                period_end
            )

            if fiscal_period is None:
                raise ValueError(
                    "Unable to resolve fiscal period for capital-cycle "
                    f"snapshot FY{fiscal_year} Q{fiscal_quarter}, "
                    f"period_end={period_end}."
                )

            if (
                fiscal_period.fiscal_year != fiscal_year
                or fiscal_period.fiscal_quarter
                != fiscal_quarter
            ):
                raise ValueError(
                    "Resolved fiscal period does not match capital-cycle "
                    f"snapshot FY{fiscal_year} Q{fiscal_quarter}."
                )

            source_state = tuple(
                (
                    metric,
                    selected[metric].source_key,
                )
                for metric in CAPITAL_CYCLE_FEATURE_METRICS
            )

            # An event date creates no new snapshot when none
            # of the six selected feature versions changed.
            if source_state == previous_source_state:
                continue

            previous_source_state = source_state

            snapshot_as_of = max(
                observation.available_at
                for observation in selected.values()
            )

            snapshots.append(
                CapitalCycleFeatureSnapshot(
                    company_id=selected[
                        "capex_growth_gap"
                    ].company_id,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=fiscal_quarter,
                    period_start=fiscal_period.period_start,
                    period_end=fiscal_period.period_end,
                    as_of=snapshot_as_of,
                    capex_growth_gap=selected[
                        "capex_growth_gap"
                    ].value,
                    capex_intensity_yoy_delta=selected[
                        "capex_intensity_yoy_delta"
                    ].value,
                    fcf_margin_yoy_delta=selected[
                        "fcf_margin_yoy_delta"
                    ].value,
                    capex_growth_gap_qoq_delta=selected[
                        "capex_growth_gap_qoq_delta"
                    ].value,
                    capex_intensity_yoy_delta_qoq_delta=selected[
                        "capex_intensity_yoy_delta_qoq_delta"
                    ].value,
                    fcf_margin_yoy_delta_qoq_delta=selected[
                        "fcf_margin_yoy_delta_qoq_delta"
                    ].value,
                    source_state=source_state,
                )
            )

    return snapshots


def select_snapshot_per_period(
    snapshots: list[CapitalCycleFeatureSnapshot],
    vintage: SnapshotVintage,
    as_of: date | None = None,
    limit: int | None = None,
) -> list[CapitalCycleFeatureSnapshot]:
    """Select one point-in-time snapshot for each fiscal period."""

    selected_by_period: dict[
        tuple[int, int],
        CapitalCycleFeatureSnapshot,
    ] = {}

    for snapshot in snapshots:
        if (
            as_of is not None
            and snapshot.as_of > as_of
        ):
            continue

        period_key = (
            snapshot.fiscal_year,
            snapshot.fiscal_quarter,
        )

        existing = selected_by_period.get(
            period_key
        )

        if existing is None:
            selected_by_period[
                period_key
            ] = snapshot
            continue

        if vintage is SnapshotVintage.FIRST:
            should_replace = (
                snapshot.as_of < existing.as_of
                or (
                    snapshot.as_of == existing.as_of
                    and snapshot.source_state
                    < existing.source_state
                )
            )

        else:
            should_replace = (
                snapshot.as_of > existing.as_of
                or (
                    snapshot.as_of == existing.as_of
                    and snapshot.source_state
                    > existing.source_state
                )
            )

        if should_replace:
            selected_by_period[
                period_key
            ] = snapshot

    selected = sorted(
        selected_by_period.values(),
        key=lambda snapshot: (
            snapshot.fiscal_year,
            snapshot.fiscal_quarter,
        ),
    )

    if limit is not None:
        selected = selected[-limit:]

    return selected


def select_latest_snapshot_per_period(
    snapshots: list[CapitalCycleFeatureSnapshot],
    as_of: date | None = None,
    limit: int | None = None,
) -> list[CapitalCycleFeatureSnapshot]:
    """Select the latest available snapshot per fiscal period."""

    return select_snapshot_per_period(
        snapshots=snapshots,
        vintage=SnapshotVintage.LATEST,
        as_of=as_of,
        limit=limit,
    )


def select_first_snapshot_per_period(
    snapshots: list[CapitalCycleFeatureSnapshot],
    as_of: date | None = None,
    limit: int | None = None,
) -> list[CapitalCycleFeatureSnapshot]:
    """Select the first complete snapshot per fiscal period."""

    return select_snapshot_per_period(
        snapshots=snapshots,
        vintage=SnapshotVintage.FIRST,
        as_of=as_of,
        limit=limit,
    )