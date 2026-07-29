from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.models import (
    Company,
    Filing,
    FinancialFact,
    FiscalPeriod,
)

PERIODIC_FORMS = {
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
}

FISCAL_PERIOD_TO_QUARTER = {
    "Q1": 1,
    "Q2": 2,
    "Q3": 3,
    "FY": 4,
}


@dataclass(frozen=True)
class FiscalPeriodCandidate:
    filing_id: int
    accession_number: str
    form: str
    filing_date: date
    report_date: date
    fiscal_year: int
    fiscal_quarter: int

def load_fiscal_period_candidates(
    session: Session,
    company_id: int,
) -> list[FiscalPeriodCandidate]:
    """Build fiscal-period candidates from SEC filing metadata."""

    statement = (
        select(
            Filing.id,
            Filing.accession_number,
            Filing.form,
            Filing.filing_date,
            Filing.report_date,
            FinancialFact.fiscal_year,
            FinancialFact.fiscal_period,
        )
        .join(
            FinancialFact,
            FinancialFact.accession_number
            == Filing.accession_number,
        )
        .where(
            Filing.company_id == company_id,
            Filing.form.in_(PERIODIC_FORMS),
            Filing.report_date.is_not(None),
            FinancialFact.fiscal_year.is_not(None),
            FinancialFact.fiscal_period.in_(
                FISCAL_PERIOD_TO_QUARTER.keys()
            ),
        )
        .distinct()
    )

    rows = session.execute(statement).all()

    labels_by_filing: dict[
        int,
        set[tuple[int, str]],
    ] = defaultdict(set)

    filing_metadata = {}

    for row in rows:
        labels_by_filing[row.id].add(
            (
                row.fiscal_year,
                row.fiscal_period,
            )
        )

        filing_metadata[row.id] = row

    candidates = []

    for filing_id, labels in labels_by_filing.items():
        if len(labels) != 1:
            raise ValueError(
                f"Filing {filing_id} has ambiguous "
                f"fiscal metadata: {labels}"
            )

        fiscal_year, fiscal_period = next(iter(labels))

        row = filing_metadata[filing_id]

        candidates.append(
            FiscalPeriodCandidate(
                filing_id=filing_id,
                accession_number=row.accession_number,
                form=row.form,
                filing_date=row.filing_date,
                report_date=row.report_date,
                fiscal_year=int(fiscal_year),
                fiscal_quarter=(
                    FISCAL_PERIOD_TO_QUARTER[
                        fiscal_period
                    ]
                ),
            )
        )

    return candidates

def select_period_filings(
    candidates: list[FiscalPeriodCandidate],
) -> dict[tuple[int, int], FiscalPeriodCandidate]:
    """Choose one filing per fiscal year and quarter."""

    selected: dict[
        tuple[int, int],
        FiscalPeriodCandidate,
    ] = {}

    for candidate in candidates:
        key = (
            candidate.fiscal_year,
            candidate.fiscal_quarter,
        )

        existing = selected.get(key)

        if existing is None:
            selected[key] = candidate
            continue

        candidate_rank = (
            candidate.form.endswith("/A"),
            candidate.filing_date,
        )

        existing_rank = (
            existing.form.endswith("/A"),
            existing.filing_date,
        )

        if candidate_rank < existing_rank:
            selected[key] = candidate

    return selected

def previous_period_key(
    fiscal_year: int,
    fiscal_quarter: int,
) -> tuple[int, int]:
    if fiscal_quarter > 1:
        return (
            fiscal_year,
            fiscal_quarter - 1,
        )

    return (
        fiscal_year - 1,
        4,
    )

def calculate_period_start(
    candidate: FiscalPeriodCandidate,
    selected: dict[
        tuple[int, int],
        FiscalPeriodCandidate,
    ],
) -> date | None:
    """Infer a quarter start from the previous quarter end."""

    previous_key = previous_period_key(
        candidate.fiscal_year,
        candidate.fiscal_quarter,
    )

    previous = selected.get(previous_key)

    if previous is None:
        return None

    return previous.report_date + timedelta(days=1)

def sync_fiscal_periods(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Create missing fiscal periods for one company."""

    candidates = load_fiscal_period_candidates(
        session,
        company.id,
    )

    selected = select_period_filings(candidates)

    inserted = 0
    existing_count = 0

    for (
        fiscal_year,
        fiscal_quarter,
    ), candidate in sorted(selected.items()):

        period_start = calculate_period_start(
            candidate,
            selected,
        )

        existing = session.scalar(
            select(FiscalPeriod).where(
                FiscalPeriod.company_id == company.id,
                FiscalPeriod.fiscal_year
                == fiscal_year,
                FiscalPeriod.fiscal_quarter
                == fiscal_quarter,
            )
        )

        if existing is not None:
            if existing.period_end != candidate.report_date:
                raise ValueError(
                    "Fiscal period end changed for "
                    f"FY{fiscal_year} Q{fiscal_quarter}: "
                    f"{existing.period_end} -> "
                    f"{candidate.report_date}"
                )

            existing_count += 1
            continue

        session.add(
            FiscalPeriod(
                company_id=company.id,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                period_start=period_start,
                period_end=candidate.report_date,
                source_filing_id=candidate.filing_id,
            )
        )

        inserted += 1

    return inserted, existing_count
