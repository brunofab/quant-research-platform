from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.models import (
    Company,
    Filing,
    FinancialFact,
    FiscalPeriod,
)

PERIODIC_FORMS = (
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
)

FISCAL_PERIOD_TO_QUARTER = {
    "Q1": 1,
    "Q2": 2,
    "Q3": 3,
    "FY": 4,
}

# Flow facts normally span approximately:
# quarter, six months, nine months, or full year.
VALID_DURATION_RANGES = (
    (80, 100),
    (170, 195),
    (260, 285),
    (350, 380),
)

# A fiscal quarter is usually roughly 13 weeks.
# The broad bounds also allow 52/53-week fiscal calendars.
PREVIOUS_PERIOD_MIN_GAP_DAYS = 70
PREVIOUS_PERIOD_MAX_GAP_DAYS = 110

TARGET_QUARTER_DAYS = 91
TARGET_FULL_YEAR_DAYS = 365


@dataclass(frozen=True)
class FiscalPeriodCandidate:
    """Authoritative fiscal-period metadata derived from a filing."""

    filing_id: int
    accession_number: str
    form: str
    filing_date: date
    report_date: date
    fiscal_year: int
    fiscal_quarter: int


@dataclass(frozen=True)
class HistoricalPeriodEvidence:
    """Raw SEC fact providing evidence for an older fiscal period end."""

    fact_id: int
    filing_id: int
    filing_date: date
    form: str
    period_end: date
    duration_days: int


def is_supported_duration(days: int) -> bool:
    """Return whether a fact spans a supported fiscal flow duration."""

    return any(
        lower <= days <= upper
        for lower, upper in VALID_DURATION_RANGES
    )


def previous_period_key(
    fiscal_year: int,
    fiscal_quarter: int,
) -> tuple[int, int]:
    """Return the fiscal year and quarter immediately before a period."""

    if fiscal_quarter > 1:
        return fiscal_year, fiscal_quarter - 1

    return fiscal_year - 1, 4


def load_fiscal_period_candidates(
    session: Session,
    company_id: int,
) -> list[FiscalPeriodCandidate]:
    """Build authoritative fiscal-period candidates from SEC filings."""

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
            FinancialFact.company_id == company_id,
            FinancialFact.fiscal_year.is_not(None),
            FinancialFact.fiscal_period.in_(
                tuple(FISCAL_PERIOD_TO_QUARTER)
            ),
        )
        .distinct()
    )

    rows = session.execute(statement).all()

    labels_by_filing: dict[
        int,
        set[tuple[int, str]],
    ] = defaultdict(set)

    filing_metadata: dict[int, Any] = {}

    for row in rows:
        labels_by_filing[row.id].add(
            (
                int(row.fiscal_year),
                str(row.fiscal_period),
            )
        )

        filing_metadata[row.id] = row

    candidates: list[FiscalPeriodCandidate] = []

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
                fiscal_year=fiscal_year,
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
    """Choose one authoritative filing per fiscal year and quarter."""

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

        # Prefer the original filing over an amendment.
        # If several originals exist, prefer the earliest filing.
        candidate_rank = (
            candidate.form.endswith("/A"),
            candidate.filing_date,
            candidate.filing_id,
        )

        existing_rank = (
            existing.form.endswith("/A"),
            existing.filing_date,
            existing.filing_id,
        )

        if candidate_rank < existing_rank:
            selected[key] = candidate

    return selected


def calculate_period_start(
    candidate: FiscalPeriodCandidate,
    selected: dict[
        tuple[int, int],
        FiscalPeriodCandidate,
    ],
) -> date | None:
    """Infer a quarter start from the previous authoritative quarter end."""

    previous = selected.get(
        previous_period_key(
            candidate.fiscal_year,
            candidate.fiscal_quarter,
        )
    )

    if previous is None:
        return None

    return previous.report_date + timedelta(days=1)


def sync_fiscal_periods(
    session: Session,
    company: Company,
) -> tuple[int, int]:
    """Create missing authoritative fiscal periods for one company."""

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
                FiscalPeriod.fiscal_year == fiscal_year,
                FiscalPeriod.fiscal_quarter == fiscal_quarter,
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
                derivation_type="filing_report_date",
                source_fact_id=None,
            )
        )

        inserted += 1

    return inserted, existing_count


def load_historical_period_evidence(
    session: Session,
    company_id: int,
    before_date: date,
) -> list[HistoricalPeriodEvidence]:
    """Load SEC facts that provide evidence of older fiscal period ends."""

    statement = (
        select(
            FinancialFact.id,
            FinancialFact.period_start,
            FinancialFact.period_end,
            Filing.id.label("filing_id"),
            Filing.filing_date,
            Filing.form,
        )
        .join(
            Filing,
            Filing.accession_number
            == FinancialFact.accession_number,
        )
        .where(
            FinancialFact.company_id == company_id,
            Filing.company_id == company_id,
            Filing.form.in_(PERIODIC_FORMS),
            FinancialFact.form.in_(PERIODIC_FORMS),
            FinancialFact.period_start.is_not(None),
            FinancialFact.period_end < before_date,
        )
    )

    evidence: list[HistoricalPeriodEvidence] = []

    for row in session.execute(statement):
        duration_days = (
            row.period_end - row.period_start
        ).days + 1

        if not is_supported_duration(duration_days):
            continue

        evidence.append(
            HistoricalPeriodEvidence(
                fact_id=row.id,
                filing_id=row.filing_id,
                filing_date=row.filing_date,
                form=row.form,
                period_end=row.period_end,
                duration_days=duration_days,
            )
        )

    return evidence


def choose_previous_period_end(
    current_end: date,
    evidence_by_end: dict[
        date,
        list[HistoricalPeriodEvidence],
    ],
) -> date | None:
    """Choose the strongest plausible immediately preceding period end."""

    candidates: list[
        tuple[int, int, date]
    ] = []

    for period_end, evidence in evidence_by_end.items():
        gap_days = (current_end - period_end).days

        if not (
            PREVIOUS_PERIOD_MIN_GAP_DAYS
            <= gap_days
            <= PREVIOUS_PERIOD_MAX_GAP_DAYS
        ):
            continue

        candidates.append(
            (
                # More independent raw facts supporting the same
                # period end make that date more credible.
                -len(evidence),

                # Among similarly supported dates, prefer a normal
                # quarter-length distance.
                abs(gap_days - TARGET_QUARTER_DAYS),

                period_end,
            )
        )

    if not candidates:
        return None

    return min(candidates)[2]


def choose_source_evidence(
    evidence: list[HistoricalPeriodEvidence],
    fiscal_quarter: int,
) -> HistoricalPeriodEvidence:
    """Choose representative SEC provenance for a historical period."""

    def form_rank(
        item: HistoricalPeriodEvidence,
    ) -> int:
        if fiscal_quarter == 4:
            if item.form == "10-K":
                return 0

            if item.form == "10-K/A":
                return 1

        else:
            if item.form == "10-Q":
                return 0

            if item.form == "10-Q/A":
                return 1

        return 2

    target_duration = (
        TARGET_FULL_YEAR_DAYS
        if fiscal_quarter == 4
        else TARGET_QUARTER_DAYS
    )

    return min(
        evidence,
        key=lambda item: (
            # Prefer 10-Q evidence for Q1-Q3 and 10-K for Q4.
            form_rank(item),

            # Prefer a quarter-duration fact for Q1-Q3 and
            # a full-year fact for Q4.
            abs(
                item.duration_days
                - target_duration
            ),

            # Prefer the earliest filing that provides the evidence.
            item.filing_date,

            # Deterministic final tie-breaker.
            item.fact_id,
        ),
    )


def refresh_period_starts(
    session: Session,
    company_id: int,
) -> None:
    """Fill and validate starts using the previous fiscal period."""

    periods = list(
        session.scalars(
            select(FiscalPeriod)
            .where(
                FiscalPeriod.company_id
                == company_id
            )
            .order_by(
                FiscalPeriod.fiscal_year,
                FiscalPeriod.fiscal_quarter,
            )
        ).all()
    )

    periods_by_key = {
        (
            period.fiscal_year,
            period.fiscal_quarter,
        ): period
        for period in periods
    }

    for period in periods:
        previous = periods_by_key.get(
            previous_period_key(
                period.fiscal_year,
                period.fiscal_quarter,
            )
        )

        if previous is None:
            # We cannot infer the start of the earliest
            # period in our available history.
            continue

        inferred_start = (
            previous.period_end
            + timedelta(days=1)
        )

        if period.period_start is None:
            period.period_start = inferred_start
            continue

        if period.period_start != inferred_start:
            raise ValueError(
                "Inconsistent fiscal period start for "
                f"FY{period.fiscal_year} "
                f"Q{period.fiscal_quarter}: "
                f"{period.period_start} != "
                f"{inferred_start}"
            )


def backfill_historical_fiscal_periods(
    session: Session,
    company: Company,
) -> int:
    """Backfill periods older than the authoritative filing history."""

    periods = list(
        session.scalars(
            select(FiscalPeriod)
            .where(
                FiscalPeriod.company_id
                == company.id
            )
            .order_by(
                FiscalPeriod.period_end
            )
        ).all()
    )

    if not periods:
        return 0

    earliest = periods[0]

    evidence = load_historical_period_evidence(
        session=session,
        company_id=company.id,
        before_date=earliest.period_end,
    )

    evidence_by_end: dict[
        date,
        list[HistoricalPeriodEvidence],
    ] = defaultdict(list)

    for item in evidence:
        evidence_by_end[
            item.period_end
        ].append(item)

    inserted = 0

    current_year = earliest.fiscal_year
    current_quarter = earliest.fiscal_quarter
    current_end = earliest.period_end

    while True:
        previous_end = choose_previous_period_end(
            current_end,
            evidence_by_end,
        )

        if previous_end is None:
            break

        previous_year, previous_quarter = (
            previous_period_key(
                current_year,
                current_quarter,
            )
        )

        source = choose_source_evidence(
            evidence_by_end[previous_end],
            previous_quarter,
        )

        existing = session.scalar(
            select(FiscalPeriod).where(
                FiscalPeriod.company_id
                == company.id,
                FiscalPeriod.fiscal_year
                == previous_year,
                FiscalPeriod.fiscal_quarter
                == previous_quarter,
            )
        )

        if existing is not None:
            if existing.period_end != previous_end:
                raise ValueError(
                    "Historical fiscal period end "
                    "conflicts for "
                    f"FY{previous_year} "
                    f"Q{previous_quarter}: "
                    f"{existing.period_end} != "
                    f"{previous_end}"
                )

        else:
            session.add(
                FiscalPeriod(
                    company_id=company.id,
                    fiscal_year=previous_year,
                    fiscal_quarter=previous_quarter,
                    period_start=None,
                    period_end=previous_end,
                    source_filing_id=source.filing_id,
                    derivation_type="raw_fact_backfill",
                    source_fact_id=source.fact_id,
                )
            )

            inserted += 1

        current_year = previous_year
        current_quarter = previous_quarter
        current_end = previous_end

    # Make newly inserted periods visible to the following query.
    session.flush()

    # Now that older periods exist, starts that were previously
    # unknown can be reconstructed.
    refresh_period_starts(
        session,
        company.id,
    )

    return inserted