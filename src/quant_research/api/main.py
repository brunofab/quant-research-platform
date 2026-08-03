from collections.abc import Iterator
from datetime import date
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Path,
    Query,
)
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from quant_research.database.connection import (
    create_database_engine,
)
from quant_research.database.models import (
    DataQualityIssue,
    DataQualityRun,
    PipelineRun,
)
from quant_research.signals.capital_cycle_features import (
    SnapshotVintage,
)
from quant_research.signals.capital_cycle_thresholds import (
    THRESHOLD_PROFILES,
    CapitalCycleThresholds,
)
from quant_research.signals.history import (
    build_company_history,
)
from quant_research.signals.universe import (
    build_universe_overview,
)

ClassifierName = Literal[
    "baseline",
    "calibrated",
    "both",
]

VintageName = Literal[
    "first",
    "latest",
]

DataQualitySeverity = Literal[
    "info",
    "warning",
    "error",
    "critical",
]

app = FastAPI(
    title="Quant Research Platform API",
    version="0.1.0",
    description=(
        "Read-only endpoints for quantitative "
        "research outputs."
    ),
)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create and reuse the SQLAlchemy engine."""

    return create_database_engine()


def get_session() -> Iterator[Session]:
    """Provide one database session per request."""

    with Session(get_engine()) as session:
        yield session


def parse_tickers(
    value: str | None,
) -> list[str] | None:
    """Parse a comma-separated ticker parameter."""

    if value is None:
        return None

    return [
        ticker.strip().upper()
        for ticker in value.split(",")
        if ticker.strip()
    ]


def resolve_threshold_profiles(
    classifier: ClassifierName,
) -> list[CapitalCycleThresholds]:
    """Resolve one or both classifier profiles."""

    if classifier == "both":
        return [
            THRESHOLD_PROFILES["baseline"],
            THRESHOLD_PROFILES["calibrated"],
        ]

    return [
        THRESHOLD_PROFILES[classifier]
    ]


def serialize_pipeline_run(
    pipeline_run: PipelineRun | None,
) -> dict[str, object] | None:
    """Convert one pipeline run to an API response."""

    if pipeline_run is None:
        return None

    return {
        "id": pipeline_run.id,
        "run_type": pipeline_run.run_type,
        "status": pipeline_run.status,
        "started_at": pipeline_run.started_at,
        "finished_at": pipeline_run.finished_at,
        "companies_total": (
            pipeline_run.companies_total
        ),
        "companies_succeeded": (
            pipeline_run.companies_succeeded
        ),
        "companies_failed": (
            pipeline_run.companies_failed
        ),
        "records_inserted": (
            pipeline_run.records_inserted
        ),
        "error_message": (
            pipeline_run.error_message
        ),
    }


def serialize_data_quality_run(
    quality_run: DataQualityRun | None,
) -> dict[str, object] | None:
    """Convert one data-quality run to an API response."""

    if quality_run is None:
        return None

    return {
        "id": quality_run.id,
        "pipeline_run_id": (
            quality_run.pipeline_run_id
        ),
        "dataset": quality_run.dataset,
        "source": quality_run.source,
        "scope_type": quality_run.scope_type,
        "scope_key": quality_run.scope_key,
        "status": quality_run.status,
        "started_at": quality_run.started_at,
        "finished_at": quality_run.finished_at,
        "checks_executed": (
            quality_run.checks_executed
        ),
        "records_checked": (
            quality_run.records_checked
        ),
        "issues_found": (
            quality_run.issues_found
        ),
        "blocking_issues": (
            quality_run.blocking_issues
        ),
        "error_message": (
            quality_run.error_message
        ),
    }


def serialize_data_quality_issue(
    issue: DataQualityIssue,
) -> dict[str, object]:
    """Convert one data-quality issue to an API response."""

    return {
        "id": issue.id,
        "data_quality_run_id": (
            issue.data_quality_run_id
        ),
        "company_id": issue.company_id,
        "entity_type": issue.entity_type,
        "entity_key": issue.entity_key,
        "dataset": issue.dataset,
        "metric": issue.metric,
        "check_name": issue.check_name,
        "severity": issue.severity,
        "blocking": issue.blocking,
        "period_start": issue.period_start,
        "period_end": issue.period_end,
        "observed_at": issue.observed_at,
        "available_at": issue.available_at,
        "actual_value": issue.actual_value,
        "expected_value": issue.expected_value,
        "message": issue.message,
        "context_json": issue.context_json,
        "created_at": issue.created_at,
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Return API and database readiness."""

    try:
        with get_engine().connect() as connection:
            connection.execute(
                text("SELECT 1")
            )

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable.",
        ) from error

    return {
        "status": "ok",
        "database": "ok",
    }


@app.get(
    "/api/v1/capital-cycle/overview"
)
def capital_cycle_overview(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
    tickers: Annotated[
        str | None,
        Query(
            description=(
                "Optional comma-separated tickers. "
                "Omit to include all stored companies."
            )
        ),
    ] = None,
    vintage: VintageName = "latest",
    classifier: ClassifierName = "baseline",
    as_of: date | None = None,
    confirmation_hits: Annotated[
        int,
        Query(ge=1),
    ] = 2,
    confirmation_window: Annotated[
        int,
        Query(ge=1),
    ] = 3,
) -> dict[str, object]:
    """Return a capital-cycle universe snapshot."""

    if confirmation_hits > confirmation_window:
        raise HTTPException(
            status_code=400,
            detail=(
                "confirmation_hits cannot exceed "
                "confirmation_window."
            ),
        )

    try:
        return build_universe_overview(
            session=session,
            requested_tickers=parse_tickers(
                tickers
            ),
            vintage=SnapshotVintage(vintage),
            as_of=as_of,
            threshold_profiles=(
                resolve_threshold_profiles(
                    classifier
                )
            ),
            confirmation_hits=confirmation_hits,
            confirmation_window=(
                confirmation_window
            ),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@app.get(
    "/api/v1/capital-cycle/history/{ticker}"
)
def capital_cycle_history(
    ticker: str,
    session: Annotated[
        Session,
        Depends(get_session),
    ],
    vintage: VintageName = "latest",
    classifier: ClassifierName = "baseline",
    as_of: date | None = None,
    confirmation_hits: Annotated[
        int,
        Query(ge=1),
    ] = 2,
    confirmation_window: Annotated[
        int,
        Query(ge=1),
    ] = 3,
    limit: Annotated[
        int | None,
        Query(ge=1, le=200),
    ] = None,
) -> dict[str, object]:
    """Return historical capital-cycle signals."""

    if confirmation_hits > confirmation_window:
        raise HTTPException(
            status_code=400,
            detail=(
                "confirmation_hits cannot exceed "
                "confirmation_window."
            ),
        )

    try:
        return build_company_history(
            session=session,
            ticker=ticker,
            vintage=SnapshotVintage(vintage),
            as_of=as_of,
            threshold_profiles=(
                resolve_threshold_profiles(
                    classifier
                )
            ),
            confirmation_hits=confirmation_hits,
            confirmation_window=(
                confirmation_window
            ),
            limit=limit,
        )

    except ValueError as error:
        message = str(error)

        status_code = (
            404
            if message.startswith(
                "Unknown company ticker"
            )
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error
    

@app.get("/api/v1/pipeline/status")
def pipeline_status(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
) -> dict[str, object]:
    """Return the latest pipeline and quality status."""

    latest_run = session.scalar(
        select(PipelineRun)
        .where(
            PipelineRun.run_type == "refresh"
        )
        .order_by(
            PipelineRun.started_at.desc(),
            PipelineRun.id.desc(),
        )
        .limit(1)
    )

    last_successful_run = session.scalar(
        select(PipelineRun)
        .where(
            PipelineRun.run_type == "refresh",
            PipelineRun.status == "succeeded",
        )
        .order_by(
            PipelineRun.finished_at.desc(),
            PipelineRun.id.desc(),
        )
        .limit(1)
    )

    latest_quality_run: (
        DataQualityRun | None
    ) = None

    if latest_run is not None:
        latest_quality_run = session.scalar(
            select(DataQualityRun)
            .where(
                DataQualityRun.pipeline_run_id
                == latest_run.id,
                DataQualityRun.dataset
                == "normalized_financials",
            )
            .order_by(
                DataQualityRun.started_at.desc(),
                DataQualityRun.id.desc(),
            )
            .limit(1)
        )

    return {
        "pipeline": "refresh",
        "has_run": latest_run is not None,
        "latest_run": serialize_pipeline_run(
            latest_run
        ),
        "last_successful_run": (
            serialize_pipeline_run(
                last_successful_run
            )
        ),
        "data_quality": (
            serialize_data_quality_run(
                latest_quality_run
            )
        ),
    }


@app.get(
    "/api/v1/data-quality/runs/{run_id}/issues"
)
def data_quality_run_issues(
    run_id: Annotated[
        int,
        Path(ge=1),
    ],
    session: Annotated[
        Session,
        Depends(get_session),
    ],
    severity: DataQualitySeverity | None = None,
    check_name: Annotated[
        str | None,
        Query(
            description=(
                "Optional exact data-quality "
                "check name."
            )
        ),
    ] = None,
    ticker: Annotated[
        str | None,
        Query(
            description=(
                "Optional company ticker."
            )
        ),
    ] = None,
    blocking_only: bool = False,
    limit: Annotated[
        int,
        Query(ge=1, le=1000),
    ] = 200,
) -> dict[str, object]:
    """Return issues belonging to one quality run."""

    quality_run = session.get(
        DataQualityRun,
        run_id,
    )

    if quality_run is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Unknown data-quality run "
                f"{run_id}."
            ),
        )

    conditions = [
        DataQualityIssue.data_quality_run_id
        == run_id
    ]

    if severity is not None:
        conditions.append(
            DataQualityIssue.severity
            == severity
        )

    normalized_check_name = (
        check_name.strip()
        if check_name
        else None
    )

    if normalized_check_name:
        conditions.append(
            DataQualityIssue.check_name
            == normalized_check_name
        )

    normalized_ticker = (
        ticker.strip().upper()
        if ticker
        else None
    )

    if normalized_ticker:
        conditions.append(
            DataQualityIssue.entity_key
            == normalized_ticker
        )

    if blocking_only:
        conditions.append(
            DataQualityIssue.blocking.is_(True)
        )

    total_issues = session.scalar(
        select(
            func.count(
                DataQualityIssue.id
            )
        ).where(*conditions)
    )

    issues = list(
        session.scalars(
            select(DataQualityIssue)
            .where(*conditions)
            .order_by(
                DataQualityIssue.blocking.desc(),
                DataQualityIssue.id.asc(),
            )
            .limit(limit)
        )
    )

    return {
        "run": serialize_data_quality_run(
            quality_run
        ),
        "filters": {
            "severity": severity,
            "check_name": (
                normalized_check_name
            ),
            "ticker": normalized_ticker,
            "blocking_only": blocking_only,
            "limit": limit,
        },
        "total_issues": total_issues or 0,
        "returned_issues": len(issues),
        "issues": [
            serialize_data_quality_issue(
                issue
            )
            for issue in issues
        ],
    }