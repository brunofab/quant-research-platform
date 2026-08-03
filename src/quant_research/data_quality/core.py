from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy.orm import Session

Severity = Literal[
    "info",
    "warning",
    "error",
    "critical",
]


@dataclass(frozen=True)
class QualityCheckContext:
    """Runtime context supplied to one quality check."""

    session: Session
    company_id: int
    ticker: str
    dataset: str
    lookback_periods: int


@dataclass(frozen=True)
class QualityIssueDraft:
    """Unpersisted issue produced by a quality check."""

    entity_type: str
    entity_key: str | None
    dataset: str
    check_name: str
    severity: Severity
    message: str

    company_id: int | None = None
    metric: str | None = None
    blocking: bool = False

    period_start: date | None = None
    period_end: date | None = None

    observed_at: datetime | None = None
    available_at: datetime | None = None

    actual_value: str | None = None
    expected_value: str | None = None

    context_json: dict[str, object] | None = None


@dataclass(frozen=True)
class QualityCheckResult:
    """Result returned by one registered check."""

    check_name: str
    records_checked: int
    issues: tuple[QualityIssueDraft, ...]


@dataclass(frozen=True)
class RegisteredQualityCheck:
    """Named quality check registered for a dataset."""

    name: str
    run: Callable[
        [QualityCheckContext],
        QualityCheckResult,
    ]
