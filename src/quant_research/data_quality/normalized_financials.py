from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import select

from quant_research.data_quality.core import (
    QualityCheckContext,
    QualityCheckResult,
    QualityIssueDraft,
    RegisteredQualityCheck,
)
from quant_research.database.models import (
    FiscalPeriod,
    NormalizedFinancial,
)

DATASET = "normalized_financials"

REQUIRED_METRICS = (
    "revenue",
    "cfo",
    "capex",
    "fcf",
)

FCF_TOLERANCE = Decimal(1)


@dataclass(frozen=True)
class FinancialPeriod:
    """One authoritative company fiscal quarter."""

    fiscal_year: int
    fiscal_quarter: int
    period_start: date | None
    period_end: date

    @property
    def key(self) -> tuple[int, int]:
        """Return the fiscal-period identity."""

        return (
            self.fiscal_year,
            self.fiscal_quarter,
        )

    @property
    def label(self) -> str:
        """Return a readable fiscal-period label."""

        return (
            f"FY{self.fiscal_year} "
            f"Q{self.fiscal_quarter}"
        )


@dataclass(frozen=True)
class FinancialObservation:
    """Relevant normalized financial observation."""

    id: int
    metric: str
    value: Decimal
    unit: str
    fiscal_year: int
    fiscal_quarter: int
    period_start: date | None
    period_end: date
    available_at: date
    derivation_type: str

    @property
    def key(
        self,
    ) -> tuple[str, int, int]:
        """Return metric and fiscal-period identity."""

        return (
            self.metric,
            self.fiscal_year,
            self.fiscal_quarter,
        )


def date_as_utc_datetime(
    value: date,
) -> datetime:
    """Represent a date at midnight UTC."""

    return datetime.combine(
        value,
        time.min,
        tzinfo=UTC,
    )


def load_recent_periods(
    context: QualityCheckContext,
) -> list[FinancialPeriod]:
    """Load the most recent authoritative quarters."""

    statement = (
        select(
            FiscalPeriod.fiscal_year,
            FiscalPeriod.fiscal_quarter,
            FiscalPeriod.period_start,
            FiscalPeriod.period_end,
        )
        .where(
            FiscalPeriod.company_id
            == context.company_id
        )
        .order_by(
            FiscalPeriod.fiscal_year.desc(),
            FiscalPeriod.fiscal_quarter.desc(),
        )
        .limit(context.lookback_periods)
    )

    rows = list(
        context.session.execute(statement)
    )

    periods = [
        FinancialPeriod(
            fiscal_year=row.fiscal_year,
            fiscal_quarter=row.fiscal_quarter,
            period_start=row.period_start,
            period_end=row.period_end,
        )
        for row in rows
    ]

    periods.reverse()

    return periods


def load_observations(
    context: QualityCheckContext,
) -> list[FinancialObservation]:
    """Load relevant quarterly normalized values."""

    statement = (
        select(
            NormalizedFinancial.id,
            NormalizedFinancial.metric,
            NormalizedFinancial.value,
            NormalizedFinancial.unit,
            NormalizedFinancial.fiscal_year,
            NormalizedFinancial.fiscal_quarter,
            NormalizedFinancial.period_start,
            NormalizedFinancial.period_end,
            NormalizedFinancial.available_at,
            NormalizedFinancial.derivation_type,
        )
        .where(
            NormalizedFinancial.company_id
            == context.company_id,
            NormalizedFinancial.period_type
            == "quarterly",
            NormalizedFinancial.metric.in_(
                REQUIRED_METRICS
            ),
            NormalizedFinancial.fiscal_quarter
            .is_not(None),
        )
    )

    observations: list[
        FinancialObservation
    ] = []

    for row in context.session.execute(
        statement
    ):
        if row.fiscal_quarter is None:
            continue

        observations.append(
            FinancialObservation(
                id=row.id,
                metric=row.metric,
                value=row.value,
                unit=row.unit,
                fiscal_year=row.fiscal_year,
                fiscal_quarter=(
                    row.fiscal_quarter
                ),
                period_start=row.period_start,
                period_end=row.period_end,
                available_at=row.available_at,
                derivation_type=(
                    row.derivation_type
                ),
            )
        )

    return observations


def group_observations(
    observations: list[FinancialObservation],
) -> dict[
    tuple[str, int, int],
    list[FinancialObservation],
]:
    """Group all vintages by metric and quarter."""

    grouped: dict[
        tuple[str, int, int],
        list[FinancialObservation],
    ] = defaultdict(list)

    for observation in observations:
        grouped[observation.key].append(
            observation
        )

    return dict(grouped)


def latest_observations(
    observations: list[FinancialObservation],
) -> list[FinancialObservation]:
    """Return all observations tied at latest date."""

    latest_date = max(
        observation.available_at
        for observation in observations
    )

    return [
        observation
        for observation in observations
        if observation.available_at
        == latest_date
    ]


def canonical_latest_observation(
    observations: list[FinancialObservation],
) -> FinancialObservation | None:
    """Return one latest row when it is unambiguous."""

    latest = latest_observations(
        observations
    )

    if len(latest) != 1:
        return None

    return latest[0]


def missing_required_metrics(
    context: QualityCheckContext,
) -> QualityCheckResult:
    """Check that recent quarters contain core metrics."""

    periods = load_recent_periods(context)
    grouped = group_observations(
        load_observations(context)
    )

    issues: list[QualityIssueDraft] = []

    for period in periods:
        for metric in REQUIRED_METRICS:
            key = (
                metric,
                period.fiscal_year,
                period.fiscal_quarter,
            )

            if key in grouped:
                continue

            issues.append(
                QualityIssueDraft(
                    company_id=context.company_id,
                    entity_type="company",
                    entity_key=context.ticker,
                    dataset=DATASET,
                    metric=metric,
                    check_name=(
                        "missing_required_metrics"
                    ),
                    severity="error",
                    blocking=False,
                    period_start=(
                        period.period_start
                    ),
                    period_end=period.period_end,
                    expected_value=(
                        "At least one normalized "
                        "quarterly observation"
                    ),
                    message=(
                        f"{context.ticker} "
                        f"{period.label} is missing "
                        f"required metric {metric}."
                    ),
                    context_json={
                        "fiscal_year": (
                            period.fiscal_year
                        ),
                        "fiscal_quarter": (
                            period.fiscal_quarter
                        ),
                        "lookback_periods": (
                            context.lookback_periods
                        ),
                    },
                )
            )

    return QualityCheckResult(
        check_name="missing_required_metrics",
        records_checked=(
            len(periods)
            * len(REQUIRED_METRICS)
        ),
        issues=tuple(issues),
    )


def duplicate_latest_observation(
    context: QualityCheckContext,
) -> QualityCheckResult:
    """Detect ambiguous current metric observations."""

    periods = load_recent_periods(context)
    period_by_key = {
        period.key: period
        for period in periods
    }

    grouped = group_observations(
        load_observations(context)
    )

    issues: list[QualityIssueDraft] = []
    records_checked = 0

    for key, observations in grouped.items():
        metric, fiscal_year, fiscal_quarter = key

        period = period_by_key.get(
            (
                fiscal_year,
                fiscal_quarter,
            )
        )

        if period is None:
            continue

        records_checked += 1

        latest = latest_observations(
            observations
        )

        if len(latest) <= 1:
            continue

        signatures = {
            (
                str(observation.value),
                observation.unit,
                observation.period_end.isoformat(),
                observation.derivation_type,
            )
            for observation in latest
        }

        severity = (
            "warning"
            if len(signatures) == 1
            else "error"
        )

        issues.append(
            QualityIssueDraft(
                company_id=context.company_id,
                entity_type="company",
                entity_key=context.ticker,
                dataset=DATASET,
                metric=metric,
                check_name=(
                    "duplicate_latest_observation"
                ),
                severity=severity,
                blocking=False,
                period_start=period.period_start,
                period_end=period.period_end,
                available_at=(
                    date_as_utc_datetime(
                        latest[0].available_at
                    )
                ),
                actual_value=(
                    f"{len(latest)} rows tied "
                    "at latest available_at"
                ),
                expected_value=(
                    "Exactly one latest observation"
                ),
                message=(
                    f"{context.ticker} "
                    f"{period.label} has "
                    f"{len(latest)} latest rows "
                    f"for metric {metric}."
                ),
                context_json={
                    "row_ids": [
                        observation.id
                        for observation in latest
                    ],
                    "latest_available_at": (
                        latest[0]
                        .available_at
                        .isoformat()
                    ),
                    "distinct_observations": (
                        len(signatures)
                    ),
                },
            )
        )

    return QualityCheckResult(
        check_name=(
            "duplicate_latest_observation"
        ),
        records_checked=records_checked,
        issues=tuple(issues),
    )


def fcf_reconciliation(
    context: QualityCheckContext,
) -> QualityCheckResult:
    """Verify FCF equals CFO minus CAPEX."""

    periods = load_recent_periods(context)
    grouped = group_observations(
        load_observations(context)
    )

    issues: list[QualityIssueDraft] = []
    records_checked = 0

    for period in periods:
        selected: dict[
            str,
            FinancialObservation,
        ] = {}

        ambiguous = False

        for metric in (
            "cfo",
            "capex",
            "fcf",
        ):
            observations = grouped.get(
                (
                    metric,
                    period.fiscal_year,
                    period.fiscal_quarter,
                )
            )

            if not observations:
                ambiguous = True
                break

            latest = (
                canonical_latest_observation(
                    observations
                )
            )

            if latest is None:
                ambiguous = True
                break

            selected[metric] = latest

        if ambiguous:
            continue

        records_checked += 1

        cfo = selected["cfo"]
        capex = selected["capex"]
        fcf = selected["fcf"]

        units = {
            cfo.unit,
            capex.unit,
            fcf.unit,
        }

        available_at = max(
            cfo.available_at,
            capex.available_at,
            fcf.available_at,
        )

        if len(units) != 1:
            issues.append(
                QualityIssueDraft(
                    company_id=context.company_id,
                    entity_type="company",
                    entity_key=context.ticker,
                    dataset=DATASET,
                    metric="fcf",
                    check_name=(
                        "fcf_reconciliation"
                    ),
                    severity="error",
                    blocking=False,
                    period_start=(
                        period.period_start
                    ),
                    period_end=period.period_end,
                    available_at=(
                        date_as_utc_datetime(
                            available_at
                        )
                    ),
                    actual_value=", ".join(
                        sorted(units)
                    ),
                    expected_value=(
                        "Identical CFO, CAPEX and "
                        "FCF units"
                    ),
                    message=(
                        f"{context.ticker} "
                        f"{period.label} cannot "
                        "reconcile FCF because the "
                        "units differ."
                    ),
                )
            )

            continue

        expected_fcf = (
            cfo.value - capex.value
        )

        difference = abs(
            fcf.value - expected_fcf
        )

        if difference <= FCF_TOLERANCE:
            continue

        issues.append(
            QualityIssueDraft(
                company_id=context.company_id,
                entity_type="company",
                entity_key=context.ticker,
                dataset=DATASET,
                metric="fcf",
                check_name="fcf_reconciliation",
                severity="error",
                blocking=False,
                period_start=period.period_start,
                period_end=period.period_end,
                available_at=(
                    date_as_utc_datetime(
                        available_at
                    )
                ),
                actual_value=str(fcf.value),
                expected_value=str(
                    expected_fcf
                ),
                message=(
                    f"{context.ticker} "
                    f"{period.label} FCF does not "
                    "equal CFO minus CAPEX."
                ),
                context_json={
                    "cfo_row_id": cfo.id,
                    "capex_row_id": capex.id,
                    "fcf_row_id": fcf.id,
                    "cfo": str(cfo.value),
                    "capex": str(capex.value),
                    "fcf": str(fcf.value),
                    "difference": str(difference),
                    "tolerance": str(
                        FCF_TOLERANCE
                    ),
                    "unit": fcf.unit,
                },
            )
        )

    return QualityCheckResult(
        check_name="fcf_reconciliation",
        records_checked=records_checked,
        issues=tuple(issues),
    )


NORMALIZED_FINANCIAL_CHECKS = (
    RegisteredQualityCheck(
        name="missing_required_metrics",
        run=missing_required_metrics,
    ),
    RegisteredQualityCheck(
        name="duplicate_latest_observation",
        run=duplicate_latest_observation,
    ),
    RegisteredQualityCheck(
        name="fcf_reconciliation",
        run=fcf_reconciliation,
    ),
)
