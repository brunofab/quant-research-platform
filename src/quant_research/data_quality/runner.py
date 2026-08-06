from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter_ns

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from quant_research.data_quality.core import (
    QualityCheckContext,
    QualityIssueDraft,
    RegisteredQualityCheck,
)
from quant_research.data_quality.normalized_financials import (
    NORMALIZED_FINANCIAL_CHECKS,
)
from quant_research.database.connection import (
    create_database_engine,
)
from quant_research.database.models import (
    Company,
    DataQualityCheckResult,
    DataQualityIssue,
    DataQualityRun,
)

CHECK_REGISTRY: dict[
    str,
    tuple[RegisteredQualityCheck, ...],
] = {
    "normalized_financials": (
        NORMALIZED_FINANCIAL_CHECKS
    ),
}


@dataclass(frozen=True)
class QualityCompany:
    """Company identity used during quality checks."""

    id: int
    ticker: str


@dataclass(frozen=True)
class DataQualitySummary:
    """Final aggregate data-quality result."""

    run_id: int
    dataset: str
    status: str
    companies_checked: int
    checks_executed: int
    records_checked: int
    issues_found: int
    blocking_issues: int


def load_companies(
    engine: Engine,
    requested_tickers: Sequence[str] | None,
) -> list[QualityCompany]:
    """Load all companies or a requested subset."""

    canonical_tickers: list[str] | None = None

    if requested_tickers is not None:
        canonical_tickers = list(
            dict.fromkeys(
                ticker.strip().upper()
                for ticker in requested_tickers
                if ticker.strip()
            )
        )

        if not canonical_tickers:
            raise ValueError(
                "At least one ticker is required."
            )

    with Session(engine) as session:
        statement = select(Company).order_by(
            Company.ticker
        )

        if canonical_tickers is not None:
            statement = statement.where(
                Company.ticker.in_(
                    canonical_tickers
                )
            )

        stored = list(
            session.scalars(statement)
        )

    by_ticker = {
        company.ticker: company
        for company in stored
    }

    if canonical_tickers is not None:
        missing = [
            ticker
            for ticker in canonical_tickers
            if ticker not in by_ticker
        ]

        if missing:
            raise ValueError(
                "Unknown company ticker(s): "
                + ", ".join(missing)
            )

        ordered = [
            by_ticker[ticker]
            for ticker in canonical_tickers
        ]
    else:
        ordered = stored

    if not ordered:
        raise ValueError(
            "No stored companies were found."
        )

    return [
        QualityCompany(
            id=company.id,
            ticker=company.ticker,
        )
        for company in ordered
    ]


def create_quality_run(
    engine: Engine,
    *,
    dataset: str,
    pipeline_run_id: int | None,
    requested_tickers: Sequence[str] | None,
    lookback_periods: int,
) -> int:
    """Create a running data-quality record."""

    scope_type = (
        "global"
        if requested_tickers is None
        else "company_set"
    )

    scope_key = (
        None
        if requested_tickers is None
        else ",".join(requested_tickers)
    )

    with Session(engine) as session:
        quality_run = DataQualityRun(
            pipeline_run_id=pipeline_run_id,
            dataset=dataset,
            source="internal",
            scope_type=scope_type,
            scope_key=scope_key,
            status="running",
            checks_executed=0,
            records_checked=0,
            issues_found=0,
            blocking_issues=0,
            context_json={
                "lookback_periods": (
                    lookback_periods
                ),
            },
        )

        session.add(quality_run)
        session.commit()
        session.refresh(quality_run)

        return quality_run.id


def persist_issue(
    session: Session,
    *,
    run_id: int,
    issue: QualityIssueDraft,
) -> None:
    """Persist one issue draft."""

    session.add(
        DataQualityIssue(
            data_quality_run_id=run_id,
            company_id=issue.company_id,
            entity_type=issue.entity_type,
            entity_key=issue.entity_key,
            dataset=issue.dataset,
            metric=issue.metric,
            check_name=issue.check_name,
            severity=issue.severity,
            blocking=issue.blocking,
            period_start=issue.period_start,
            period_end=issue.period_end,
            observed_at=issue.observed_at,
            available_at=issue.available_at,
            actual_value=issue.actual_value,
            expected_value=issue.expected_value,
            message=issue.message,
            context_json=issue.context_json,
        )
    )

def persist_check_result(
    session: Session,
    *,
    run_id: int,
    company: QualityCompany,
    dataset: str,
    check_name: str,
    execution_order: int,
    status: str,
    records_checked: int,
    issues_found: int,
    blocking_issues: int,
    started_at: datetime,
    finished_at: datetime,
    duration_ms: int,
    error_message: str | None = None,
) -> None:
    """Persist one executed quality-check result."""

    session.add(
        DataQualityCheckResult(
            data_quality_run_id=run_id,
            company_id=company.id,
            scope_type="company",
            scope_key=company.ticker,
            dataset=dataset,
            check_name=check_name,
            execution_order=execution_order,
            status=status,
            records_checked=records_checked,
            issues_found=issues_found,
            blocking_issues=blocking_issues,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error_message=(
                error_message[:10_000]
                if error_message
                else None
            ),
        )
    )



def finish_quality_run(
    engine: Engine,
    *,
    run_id: int,
    status: str,
    checks_executed: int,
    records_checked: int,
    issues_found: int,
    blocking_issues: int,
    error_message: str | None = None,
) -> None:
    """Persist the final run state."""

    with Session(engine) as session:
        quality_run = session.get(
            DataQualityRun,
            run_id,
        )

        if quality_run is None:
            raise RuntimeError(
                f"Data-quality run {run_id} "
                "was not found."
            )

        quality_run.status = status
        quality_run.finished_at = datetime.now(
            UTC
        )
        quality_run.checks_executed = (
            checks_executed
        )
        quality_run.records_checked = (
            records_checked
        )
        quality_run.issues_found = issues_found
        quality_run.blocking_issues = (
            blocking_issues
        )
        quality_run.error_message = (
            error_message[:10_000]
            if error_message
            else None
        )

        session.commit()


def resolve_status(
    *,
    issues_found: int,
    blocking_issues: int,
) -> str:
    """Resolve the quality-run status."""

    if blocking_issues > 0:
        return "failed"

    if issues_found > 0:
        return "warning"

    return "passed"


def run_data_quality(
    *,
    dataset: str,
    requested_tickers: Sequence[str] | None,
    pipeline_run_id: int | None = None,
    lookback_periods: int = 12,
) -> DataQualitySummary:
    """Run all registered checks for one dataset."""

    if lookback_periods < 1:
        raise ValueError(
            "lookback_periods must be positive."
        )

    checks = CHECK_REGISTRY.get(dataset)

    if checks is None:
        raise ValueError(
            f"No checks are registered for "
            f"dataset {dataset}."
        )

    engine = create_database_engine()

    companies = load_companies(
        engine=engine,
        requested_tickers=requested_tickers,
    )

    run_id = create_quality_run(
        engine=engine,
        dataset=dataset,
        pipeline_run_id=pipeline_run_id,
        requested_tickers=requested_tickers,
        lookback_periods=lookback_periods,
    )

    checks_executed = 0
    records_checked = 0
    issues_found = 0
    blocking_issues = 0

    print(
        f"Data-quality run {run_id} started "
        f"for {len(companies)} companies."
    )

    try:
        with Session(engine) as session:
            for company in companies:
                print()
                print("=" * 72)
                print(
                    f"{company.ticker}: {dataset}"
                )
                print("=" * 72)

                context = QualityCheckContext(
                    session=session,
                    company_id=company.id,
                    ticker=company.ticker,
                    dataset=dataset,
                    lookback_periods=(
                        lookback_periods
                    ),
                )

                for check in checks:
                    execution_order = (
                        checks_executed + 1
                    )

                    check_started_at = (
                        datetime.now(UTC)
                    )

                    check_started_ns = (
                        perf_counter_ns()
                    )

                    try:
                        result = check.run(context)

                        if (
                            result.check_name
                            != check.name
                        ):
                            raise RuntimeError(
                                f"Check {check.name} "
                                "returned a mismatched "
                                "check name."
                            )

                        check_issues_found = len(
                            result.issues
                        )

                        check_blocking_issues = sum(
                            1
                            for issue in result.issues
                            if issue.blocking
                        )

                        check_status = resolve_status(
                            issues_found=(
                                check_issues_found
                            ),
                            blocking_issues=(
                                check_blocking_issues
                            ),
                        )

                        check_finished_at = (
                            datetime.now(UTC)
                        )

                        duration_ms = max(
                            0,
                            (
                                perf_counter_ns()
                                - check_started_ns
                            )
                            // 1_000_000,
                        )

                        for issue in result.issues:
                            persist_issue(
                                session,
                                run_id=run_id,
                                issue=issue,
                            )

                        persist_check_result(
                            session,
                            run_id=run_id,
                            company=company,
                            dataset=dataset,
                            check_name=check.name,
                            execution_order=(
                                execution_order
                            ),
                            status=check_status,
                            records_checked=(
                                result.records_checked
                            ),
                            issues_found=(
                                check_issues_found
                            ),
                            blocking_issues=(
                                check_blocking_issues
                            ),
                            started_at=(
                                check_started_at
                            ),
                            finished_at=(
                                check_finished_at
                            ),
                            duration_ms=duration_ms,
                        )

                        session.commit()

                    except Exception as error:
                        check_finished_at = (
                            datetime.now(UTC)
                        )

                        duration_ms = max(
                            0,
                            (
                                perf_counter_ns()
                                - check_started_ns
                            )
                            // 1_000_000,
                        )

                        session.rollback()

                        checks_executed = (
                            execution_order
                        )

                        try:
                            persist_check_result(
                                session,
                                run_id=run_id,
                                company=company,
                                dataset=dataset,
                                check_name=check.name,
                                execution_order=(
                                    execution_order
                                ),
                                status="failed",
                                records_checked=0,
                                issues_found=0,
                                blocking_issues=0,
                                started_at=(
                                    check_started_at
                                ),
                                finished_at=(
                                    check_finished_at
                                ),
                                duration_ms=duration_ms,
                                error_message=(
                                    f"{type(error).__name__}: "
                                    f"{error}"
                                ),
                            )

                            session.commit()

                        except SQLAlchemyError:
                            session.rollback()

                        raise

                    checks_executed = (
                        execution_order
                    )

                    records_checked += (
                        result.records_checked
                    )

                    issues_found += (
                        check_issues_found
                    )

                    blocking_issues += (
                        check_blocking_issues
                    )

                    print(
                        f"{check.name}: "
                        f"{result.records_checked} "
                        "records checked, "
                        f"{check_issues_found} "
                        "issues."
                    )

        status = resolve_status(
            issues_found=issues_found,
            blocking_issues=blocking_issues,
        )

        finish_quality_run(
            engine=engine,
            run_id=run_id,
            status=status,
            checks_executed=checks_executed,
            records_checked=records_checked,
            issues_found=issues_found,
            blocking_issues=blocking_issues,
        )

    except Exception as error:
        finish_quality_run(
            engine=engine,
            run_id=run_id,
            status="failed",
            checks_executed=checks_executed,
            records_checked=records_checked,
            issues_found=issues_found,
            blocking_issues=blocking_issues,
            error_message=str(error),
        )

        raise

    finally:
        engine.dispose()

    print()
    print("=" * 72)
    print(f"Data-quality run {run_id} finished.")
    print(f"Status: {status}")
    print(
        f"Companies checked: {len(companies)}"
    )
    print(
        f"Checks executed: {checks_executed}"
    )
    print(
        f"Records checked: {records_checked}"
    )
    print(f"Issues found: {issues_found}")
    print(
        f"Blocking issues: {blocking_issues}"
    )
    print("=" * 72)

    return DataQualitySummary(
        run_id=run_id,
        dataset=dataset,
        status=status,
        companies_checked=len(companies),
        checks_executed=checks_executed,
        records_checked=records_checked,
        issues_found=issues_found,
        blocking_issues=blocking_issues,
    )
