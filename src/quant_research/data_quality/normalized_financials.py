from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from itertools import pairwise
from statistics import median

from sqlalchemy import select

from quant_research.data_quality.core import (
    QualityCheckContext,
    QualityCheckResult,
    QualityIssueDraft,
    RegisteredQualityCheck,
)
from quant_research.database.models import (
    Filing,
    FiscalPeriod,
    NormalizedFinancial,
    NormalizedFinancialDependency,
    NormalizedFinancialSource,
)

DATASET = "normalized_financials"
PERIOD_TYPE = "quarter"

REQUIRED_METRICS = (
    "revenue",
    "cfo",
    "capex",
    "fcf",
)

FCF_TOLERANCE = Decimal(1)

PERIODIC_FORMS = (
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
)

SOURCE_FRESHNESS_HISTORY_LIMIT = 8
SOURCE_FRESHNESS_MINIMUM_DAYS = 130
SOURCE_FRESHNESS_GRACE_DAYS = 30
SOURCE_FRESHNESS_MAXIMUM_DAYS = 180


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


@dataclass(frozen=True)
class SourceFilingObservation:
    """Authoritative filing associated with one fiscal period."""

    filing_id: int
    form: str
    filing_date: date
    fiscal_year: int
    fiscal_quarter: int
    period_start: date | None
    period_end: date

    @property
    def label(self) -> str:
        """Return a readable fiscal-period label."""

        return (
            f"FY{self.fiscal_year} "
            f"Q{self.fiscal_quarter}"
        )


@dataclass(frozen=True)
class LineageAssessment:
    """Result of recursively tracing one normalized row."""

    complete: bool
    missing_leaf_ids: frozenset[int]
    cycle_detected: bool


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
            == PERIOD_TYPE,
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


def load_recent_source_filings(
    context: QualityCheckContext,
) -> list[SourceFilingObservation]:
    """Load recent authoritative fiscal-period filings."""

    statement = (
        select(
            Filing.id.label("filing_id"),
            Filing.form,
            Filing.filing_date,
            FiscalPeriod.fiscal_year,
            FiscalPeriod.fiscal_quarter,
            FiscalPeriod.period_start,
            FiscalPeriod.period_end,
        )
        .join(
            Filing,
            Filing.id
            == FiscalPeriod.source_filing_id,
        )
        .where(
            FiscalPeriod.company_id
            == context.company_id,
            Filing.form.in_(PERIODIC_FORMS),
        )
        .order_by(
            FiscalPeriod.period_end.desc(),
            Filing.filing_date.desc(),
            Filing.id.desc(),
        )
        .limit(
            SOURCE_FRESHNESS_HISTORY_LIMIT
        )
    )

    return [
        SourceFilingObservation(
            filing_id=row.filing_id,
            form=row.form,
            filing_date=row.filing_date,
            fiscal_year=row.fiscal_year,
            fiscal_quarter=row.fiscal_quarter,
            period_start=row.period_start,
            period_end=row.period_end,
        )
        for row in context.session.execute(
            statement
        )
    ]


def filing_intervals_in_days(
    filings: list[SourceFilingObservation],
) -> list[int]:
    """Calculate positive intervals between filing dates."""

    filing_dates = sorted(
        {
            filing.filing_date
            for filing in filings
        }
    )
    return [
        (current_date - previous_date).days
        for previous_date, current_date
        in pairwise(filing_dates)
        if current_date > previous_date
    ]


def source_freshness_threshold_days(
    intervals: list[int],
) -> tuple[int, int | None]:
    """Resolve a robust filing-age warning threshold."""

    if not intervals:
        return (
            SOURCE_FRESHNESS_MINIMUM_DAYS,
            None,
        )

    typical_interval = int(
        median(intervals)
    )

    threshold = max(
        SOURCE_FRESHNESS_MINIMUM_DAYS,
        typical_interval
        + SOURCE_FRESHNESS_GRACE_DAYS,
    )

    threshold = min(
        threshold,
        SOURCE_FRESHNESS_MAXIMUM_DAYS,
    )

    return threshold, typical_interval


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


def load_latest_required_observations(
    context: QualityCheckContext,
) -> list[FinancialObservation]:
    """Load one unambiguous latest row per metric and quarter."""

    periods = load_recent_periods(context)

    grouped = group_observations(
        load_observations(context)
    )

    selected: list[
        FinancialObservation
    ] = []

    for period in periods:
        for metric in REQUIRED_METRICS:
            observations = grouped.get(
                (
                    metric,
                    period.fiscal_year,
                    period.fiscal_quarter,
                )
            )

            if not observations:
                continue

            latest = canonical_latest_observation(
                observations
            )

            if latest is None:
                continue

            selected.append(latest)

    return selected


def load_lineage_graph(
    context: QualityCheckContext,
    root_ids: set[int],
) -> tuple[
    dict[int, frozenset[int]],
    dict[int, int],
]:
    """Load every dependency reachable from the roots."""

    dependencies: dict[
        int,
        set[int],
    ] = defaultdict(set)

    raw_source_counts: dict[
        int,
        int,
    ] = defaultdict(int)

    visited: set[int] = set()
    frontier = set(root_ids)

    while frontier:
        batch = frontier - visited

        if not batch:
            break

        visited.update(batch)

        raw_source_ids = context.session.scalars(
            select(
                NormalizedFinancialSource
                .normalized_financial_id
            ).where(
                NormalizedFinancialSource
                .normalized_financial_id
                .in_(batch)
            )
        )

        for normalized_id in raw_source_ids:
            raw_source_counts[
                normalized_id
            ] += 1

        dependency_rows = (
            context.session.execute(
                select(
                    NormalizedFinancialDependency
                    .derived_financial_id,
                    NormalizedFinancialDependency
                    .source_financial_id,
                ).where(
                    NormalizedFinancialDependency
                    .derived_financial_id
                    .in_(batch)
                )
            )
        )

        next_frontier: set[int] = set()

        for row in dependency_rows:
            derived_id = (
                row.derived_financial_id
            )

            source_id = (
                row.source_financial_id
            )

            dependencies[
                derived_id
            ].add(source_id)

            if source_id not in visited:
                next_frontier.add(source_id)

        frontier = next_frontier

    frozen_dependencies = {
        normalized_id: frozenset(
            source_ids
        )
        for normalized_id, source_ids
        in dependencies.items()
    }

    return (
        frozen_dependencies,
        dict(raw_source_counts),
    )


def assess_lineage(
    normalized_id: int,
    dependencies: dict[
        int,
        frozenset[int],
    ],
    raw_source_counts: dict[int, int],
    memo: dict[int, LineageAssessment],
    active_path: set[int],
) -> LineageAssessment:
    """Recursively determine whether lineage reaches raw facts."""

    cached = memo.get(normalized_id)

    if cached is not None:
        return cached

    if normalized_id in active_path:
        return LineageAssessment(
            complete=False,
            missing_leaf_ids=frozenset(),
            cycle_detected=True,
        )

    source_ids = dependencies.get(
        normalized_id,
        frozenset(),
    )

    if not source_ids:
        if (
            raw_source_counts.get(
                normalized_id,
                0,
            )
            > 0
        ):
            result = LineageAssessment(
                complete=True,
                missing_leaf_ids=frozenset(),
                cycle_detected=False,
            )

        else:
            result = LineageAssessment(
                complete=False,
                missing_leaf_ids=frozenset(
                    {normalized_id}
                ),
                cycle_detected=False,
            )

        memo[normalized_id] = result

        return result

    active_path.add(normalized_id)

    try:
        child_results = [
            assess_lineage(
                normalized_id=source_id,
                dependencies=dependencies,
                raw_source_counts=(
                    raw_source_counts
                ),
                memo=memo,
                active_path=active_path,
            )
            for source_id in source_ids
        ]

    finally:
        active_path.remove(normalized_id)

    missing_leaf_ids = frozenset().union(
        *(
            result.missing_leaf_ids
            for result in child_results
        )
    )

    result = LineageAssessment(
        complete=all(
            child.complete
            for child in child_results
        ),
        missing_leaf_ids=missing_leaf_ids,
        cycle_detected=any(
            child.cycle_detected
            for child in child_results
        ),
    )

    memo[normalized_id] = result

    return result


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

def lineage_completeness(
    context: QualityCheckContext,
) -> QualityCheckResult:
    """Verify that normalized values resolve to raw facts."""

    observations = (
        load_latest_required_observations(
            context
        )
    )

    root_ids = {
        observation.id
        for observation in observations
    }

    (
        dependencies,
        raw_source_counts,
    ) = load_lineage_graph(
        context=context,
        root_ids=root_ids,
    )

    memo: dict[
        int,
        LineageAssessment,
    ] = {}

    issues: list[
        QualityIssueDraft
    ] = []

    for observation in observations:
        assessment = assess_lineage(
            normalized_id=observation.id,
            dependencies=dependencies,
            raw_source_counts=(
                raw_source_counts
            ),
            memo=memo,
            active_path=set(),
        )

        if assessment.complete:
            continue

        reasons: list[str] = []

        if assessment.missing_leaf_ids:
            reasons.append(
                "one or more lineage leaves have "
                "neither raw sources nor dependencies"
            )

        if assessment.cycle_detected:
            reasons.append(
                "a dependency cycle was detected"
            )

        reason_text = (
            "; ".join(reasons)
            if reasons
            else "no complete raw-data path exists"
        )

        fiscal_label = (
            f"FY{observation.fiscal_year} "
            f"Q{observation.fiscal_quarter}"
        )

        issues.append(
            QualityIssueDraft(
                company_id=context.company_id,
                entity_type="company",
                entity_key=context.ticker,
                dataset=DATASET,
                metric=observation.metric,
                check_name=(
                    "lineage_completeness"
                ),
                severity="error",
                blocking=False,
                period_start=(
                    observation.period_start
                ),
                period_end=observation.period_end,
                available_at=(
                    date_as_utc_datetime(
                        observation.available_at
                    )
                ),
                actual_value=(
                    "Incomplete normalized-financial "
                    "lineage"
                ),
                expected_value=(
                    "Every dependency branch resolves "
                    "to at least one financial_fact"
                ),
                message=(
                    f"{context.ticker} "
                    f"{fiscal_label} "
                    f"{observation.metric} has "
                    f"incomplete lineage: "
                    f"{reason_text}."
                ),
                context_json={
                    "normalized_financial_id": (
                        observation.id
                    ),
                    "derivation_type": (
                        observation.derivation_type
                    ),
                    "direct_raw_source_count": (
                        raw_source_counts.get(
                            observation.id,
                            0,
                        )
                    ),
                    "immediate_dependency_ids": (
                        sorted(
                            dependencies.get(
                                observation.id,
                                frozenset(),
                            )
                        )
                    ),
                    "missing_leaf_ids": sorted(
                        assessment.missing_leaf_ids
                    ),
                    "cycle_detected": (
                        assessment.cycle_detected
                    ),
                },
            )
        )

    return QualityCheckResult(
        check_name="lineage_completeness",
        records_checked=len(observations),
        issues=tuple(issues),
    )

def fiscal_period_consistency(
    context: QualityCheckContext,
) -> QualityCheckResult:
    """Verify normalized dates against fiscal periods."""

    periods = load_recent_periods(context)

    period_by_key = {
        period.key: period
        for period in periods
    }

    observations = (
        load_latest_required_observations(
            context
        )
    )

    issues: list[
        QualityIssueDraft
    ] = []

    for observation in observations:
        fiscal_period = period_by_key.get(
            (
                observation.fiscal_year,
                observation.fiscal_quarter,
            )
        )

        if fiscal_period is None:
            issues.append(
                QualityIssueDraft(
                    company_id=context.company_id,
                    entity_type="company",
                    entity_key=context.ticker,
                    dataset=DATASET,
                    metric=observation.metric,
                    check_name=(
                        "fiscal_period_consistency"
                    ),
                    severity="error",
                    blocking=False,
                    period_start=(
                        observation.period_start
                    ),
                    period_end=(
                        observation.period_end
                    ),
                    available_at=(
                        date_as_utc_datetime(
                            observation.available_at
                        )
                    ),
                    actual_value=(
                        "Normalized financial exists "
                        "without a matching fiscal "
                        "period"
                    ),
                    expected_value=(
                        "Matching fiscal_periods row"
                    ),
                    message=(
                        f"{context.ticker} "
                        f"FY{observation.fiscal_year} "
                        f"Q{observation.fiscal_quarter} "
                        f"{observation.metric} has no "
                        "matching fiscal-period record."
                    ),
                    context_json={
                        "normalized_financial_id": (
                            observation.id
                        ),
                        "fiscal_year": (
                            observation.fiscal_year
                        ),
                        "fiscal_quarter": (
                            observation.fiscal_quarter
                        ),
                        "normalized_period_start": (
                            observation.period_start
                            .isoformat()
                            if observation.period_start
                            else None
                        ),
                        "normalized_period_end": (
                            observation.period_end
                            .isoformat()
                        ),
                    },
                )
            )

            continue

        start_matches = (
            observation.period_start
            == fiscal_period.period_start
        )

        end_matches = (
            observation.period_end
            == fiscal_period.period_end
        )

        if start_matches and end_matches:
            continue

        fiscal_label = (
            f"FY{observation.fiscal_year} "
            f"Q{observation.fiscal_quarter}"
        )

        normalized_start = (
            observation.period_start.isoformat()
            if observation.period_start
            else None
        )

        expected_start = (
            fiscal_period.period_start.isoformat()
            if fiscal_period.period_start
            else None
        )

        issues.append(
            QualityIssueDraft(
                company_id=context.company_id,
                entity_type="company",
                entity_key=context.ticker,
                dataset=DATASET,
                metric=observation.metric,
                check_name=(
                    "fiscal_period_consistency"
                ),
                severity="error",
                blocking=False,
                period_start=(
                    observation.period_start
                ),
                period_end=observation.period_end,
                available_at=(
                    date_as_utc_datetime(
                        observation.available_at
                    )
                ),
                actual_value=(
                    "period_start="
                    f"{normalized_start}, "
                    "period_end="
                    f"{observation.period_end}"
                ),
                expected_value=(
                    "period_start="
                    f"{expected_start}, "
                    "period_end="
                    f"{fiscal_period.period_end}"
                ),
                message=(
                    f"{context.ticker} "
                    f"{fiscal_label} "
                    f"{observation.metric} does not "
                    "match the authoritative fiscal "
                    "period."
                ),
                context_json={
                    "normalized_financial_id": (
                        observation.id
                    ),
                    "fiscal_year": (
                        observation.fiscal_year
                    ),
                    "fiscal_quarter": (
                        observation.fiscal_quarter
                    ),
                    "normalized_period_start": (
                        normalized_start
                    ),
                    "expected_period_start": (
                        expected_start
                    ),
                    "normalized_period_end": (
                        observation.period_end
                        .isoformat()
                    ),
                    "expected_period_end": (
                        fiscal_period.period_end
                        .isoformat()
                    ),
                    "start_matches": (
                        start_matches
                    ),
                    "end_matches": end_matches,
                },
            )
        )

    return QualityCheckResult(
        check_name=(
            "fiscal_period_consistency"
        ),
        records_checked=len(observations),
        issues=tuple(issues),
    )


def latest_period_freshness(
    context: QualityCheckContext,
) -> QualityCheckResult:
    """Verify that core metrics reach the latest fiscal period."""

    periods = load_recent_periods(context)

    if not periods:
        issue = QualityIssueDraft(
            company_id=context.company_id,
            entity_type="company",
            entity_key=context.ticker,
            dataset=DATASET,
            metric=None,
            check_name="latest_period_freshness",
            severity="error",
            blocking=False,
            actual_value="No fiscal periods available",
            expected_value=(
                "At least one authoritative "
                "fiscal period"
            ),
            message=(
                f"{context.ticker} has no fiscal "
                "period available for the freshness "
                "check."
            ),
            context_json={
                "lookback_periods": (
                    context.lookback_periods
                ),
            },
        )

        return QualityCheckResult(
            check_name="latest_period_freshness",
            records_checked=1,
            issues=(issue,),
        )

    expected_period = max(
        periods,
        key=lambda period: period.key,
    )

    observations = load_observations(context)

    observations_by_metric: dict[
        str,
        list[FinancialObservation],
    ] = defaultdict(list)

    for observation in observations:
        observations_by_metric[
            observation.metric
        ].append(observation)

    issues: list[QualityIssueDraft] = []

    for metric in REQUIRED_METRICS:
        metric_observations = (
            observations_by_metric.get(
                metric,
                [],
            )
        )

        if not metric_observations:
            issues.append(
                QualityIssueDraft(
                    company_id=context.company_id,
                    entity_type="company",
                    entity_key=context.ticker,
                    dataset=DATASET,
                    metric=metric,
                    check_name=(
                        "latest_period_freshness"
                    ),
                    severity="error",
                    blocking=False,
                    period_start=(
                        expected_period.period_start
                    ),
                    period_end=(
                        expected_period.period_end
                    ),
                    actual_value=(
                        "No normalized quarterly "
                        "observations"
                    ),
                    expected_value=(
                        expected_period.label
                    ),
                    message=(
                        f"{context.ticker} has no "
                        f"normalized {metric} data, "
                        f"while the latest fiscal "
                        f"period is "
                        f"{expected_period.label}."
                    ),
                    context_json={
                        "expected_fiscal_year": (
                            expected_period.fiscal_year
                        ),
                        "expected_fiscal_quarter": (
                            expected_period
                            .fiscal_quarter
                        ),
                        "expected_period_end": (
                            expected_period
                            .period_end
                            .isoformat()
                        ),
                    },
                )
            )

            continue

        latest_metric_key = max(
            (
                observation.fiscal_year,
                observation.fiscal_quarter,
            )
            for observation
            in metric_observations
        )

        latest_metric_rows = [
            observation
            for observation
            in metric_observations
            if (
                observation.fiscal_year,
                observation.fiscal_quarter,
            )
            == latest_metric_key
        ]

        if latest_metric_key == expected_period.key:
            continue

        expected_ordinal = (
            expected_period.fiscal_year * 4
            + expected_period.fiscal_quarter
        )

        actual_ordinal = (
            latest_metric_key[0] * 4
            + latest_metric_key[1]
        )

        period_difference = (
            expected_ordinal - actual_ordinal
        )

        latest_available_at = max(
            observation.available_at
            for observation
            in latest_metric_rows
        )

        latest_period_end = max(
            observation.period_end
            for observation
            in latest_metric_rows
        )

        if period_difference > 0:
            direction = "behind"

            message = (
                f"{context.ticker} {metric} is "
                f"{period_difference} fiscal "
                "period(s) behind the latest "
                f"known period "
                f"{expected_period.label}."
            )

        else:
            direction = "ahead"

            message = (
                f"{context.ticker} {metric} is "
                f"{abs(period_difference)} fiscal "
                "period(s) ahead of the latest "
                "known fiscal-period record."
            )

        actual_label = (
            f"FY{latest_metric_key[0]} "
            f"Q{latest_metric_key[1]}"
        )

        issues.append(
            QualityIssueDraft(
                company_id=context.company_id,
                entity_type="company",
                entity_key=context.ticker,
                dataset=DATASET,
                metric=metric,
                check_name=(
                    "latest_period_freshness"
                ),
                severity="error",
                blocking=False,
                period_start=(
                    expected_period.period_start
                ),
                period_end=(
                    expected_period.period_end
                ),
                available_at=(
                    date_as_utc_datetime(
                        latest_available_at
                    )
                ),
                actual_value=actual_label,
                expected_value=(
                    expected_period.label
                ),
                message=message,
                context_json={
                    "direction": direction,
                    "expected_fiscal_year": (
                        expected_period.fiscal_year
                    ),
                    "expected_fiscal_quarter": (
                        expected_period
                        .fiscal_quarter
                    ),
                    "expected_period_end": (
                        expected_period
                        .period_end
                        .isoformat()
                    ),
                    "latest_metric_fiscal_year": (
                        latest_metric_key[0]
                    ),
                    "latest_metric_fiscal_quarter": (
                        latest_metric_key[1]
                    ),
                    "latest_metric_period_end": (
                        latest_period_end.isoformat()
                    ),
                    "periods_behind": (
                        max(0, period_difference)
                    ),
                    "periods_ahead": (
                        abs(period_difference)
                        if period_difference < 0
                        else 0
                    ),
                    "latest_available_at": (
                        latest_available_at
                        .isoformat()
                    ),
                    "latest_row_ids": [
                        observation.id
                        for observation
                        in latest_metric_rows
                    ],
                },
            )
        )

    return QualityCheckResult(
        check_name="latest_period_freshness",
        records_checked=len(REQUIRED_METRICS),
        issues=tuple(issues),
    )


def latest_source_freshness(
    context: QualityCheckContext,
) -> QualityCheckResult:
    """Check the age of the latest authoritative filing."""

    observed_at = datetime.now(UTC)

    filings = load_recent_source_filings(
        context
    )

    if not filings:
        issue = QualityIssueDraft(
            company_id=context.company_id,
            entity_type="company",
            entity_key=context.ticker,
            dataset=DATASET,
            metric=None,
            check_name=(
                "latest_source_freshness"
            ),
            severity="warning",
            blocking=False,
            observed_at=observed_at,
            actual_value=(
                "No authoritative periodic "
                "filing available"
            ),
            expected_value=(
                "At least one 10-Q or 10-K "
                "linked to a fiscal period"
            ),
            message=(
                f"{context.ticker} has no "
                "authoritative periodic filing "
                "available for source-freshness "
                "validation."
            ),
            context_json={
                "history_limit": (
                    SOURCE_FRESHNESS_HISTORY_LIMIT
                ),
                "periodic_forms": list(
                    PERIODIC_FORMS
                ),
            },
        )

        return QualityCheckResult(
            check_name=(
                "latest_source_freshness"
            ),
            records_checked=1,
            issues=(issue,),
        )

    latest_filing = filings[0]

    intervals = filing_intervals_in_days(
        filings
    )

    (
        warning_threshold_days,
        typical_interval_days,
    ) = source_freshness_threshold_days(
        intervals
    )

    filing_age_days = (
        observed_at.date()
        - latest_filing.filing_date
    ).days

    if (
        0
        <= filing_age_days
        <= warning_threshold_days
    ):
        return QualityCheckResult(
            check_name=(
                "latest_source_freshness"
            ),
            records_checked=1,
            issues=(),
        )

    if filing_age_days < 0:
        severity = "error"

        message = (
            f"{context.ticker} latest "
            f"authoritative filing "
            f"{latest_filing.filing_id} has a "
            "filing date in the future."
        )

    else:
        severity = "warning"

        message = (
            f"{context.ticker} latest "
            f"authoritative filing is "
            f"{filing_age_days} days old, "
            f"exceeding the adaptive "
            f"{warning_threshold_days}-day "
            "freshness threshold."
        )

    issue = QualityIssueDraft(
        company_id=context.company_id,
        entity_type="company",
        entity_key=context.ticker,
        dataset=DATASET,
        metric=None,
        check_name=(
            "latest_source_freshness"
        ),
        severity=severity,
        blocking=False,
        period_start=(
            latest_filing.period_start
        ),
        period_end=latest_filing.period_end,
        observed_at=observed_at,
        available_at=(
            date_as_utc_datetime(
                latest_filing.filing_date
            )
        ),
        actual_value=(
            f"{filing_age_days} days since "
            "latest filing"
        ),
        expected_value=(
            "No more than "
            f"{warning_threshold_days} days"
        ),
        message=message,
        context_json={
            "filing_id": (
                latest_filing.filing_id
            ),
            "form": latest_filing.form,
            "filing_date": (
                latest_filing.filing_date
                .isoformat()
            ),
            "fiscal_year": (
                latest_filing.fiscal_year
            ),
            "fiscal_quarter": (
                latest_filing.fiscal_quarter
            ),
            "fiscal_period": (
                latest_filing.label
            ),
            "period_end": (
                latest_filing.period_end
                .isoformat()
            ),
            "filing_age_days": (
                filing_age_days
            ),
            "warning_threshold_days": (
                warning_threshold_days
            ),
            "typical_interval_days": (
                typical_interval_days
            ),
            "observed_intervals_days": (
                intervals
            ),
            "history_limit": (
                SOURCE_FRESHNESS_HISTORY_LIMIT
            ),
            "minimum_threshold_days": (
                SOURCE_FRESHNESS_MINIMUM_DAYS
            ),
            "grace_days": (
                SOURCE_FRESHNESS_GRACE_DAYS
            ),
            "maximum_threshold_days": (
                SOURCE_FRESHNESS_MAXIMUM_DAYS
            ),
        },
    )

    return QualityCheckResult(
        check_name=(
            "latest_source_freshness"
        ),
        records_checked=1,
        issues=(issue,),
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
    RegisteredQualityCheck(
        name="lineage_completeness",
        run=lineage_completeness,
    ),
    RegisteredQualityCheck(
        name="fiscal_period_consistency",
        run=fiscal_period_consistency,
    ),
    RegisteredQualityCheck(
        name="latest_period_freshness",
        run=latest_period_freshness,
    ),
    RegisteredQualityCheck(
        name="latest_source_freshness",
        run=latest_source_freshness,
    ),
)
