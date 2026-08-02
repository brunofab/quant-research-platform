from collections.abc import Iterator
from datetime import date
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from quant_research.database.connection import (
    create_database_engine,
)
from quant_research.signals.capital_cycle_features import (
    SnapshotVintage,
)
from quant_research.signals.capital_cycle_thresholds import (
    THRESHOLD_PROFILES,
    CapitalCycleThresholds,
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
