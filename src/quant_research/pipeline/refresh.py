from __future__ import annotations

import shlex
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from quant_research.database.connection import (
    create_database_engine,
)
from quant_research.database.models import (
    Company,
    Filing,
    FinancialFact,
    FiscalPeriod,
    NormalizedFinancial,
    PipelineRun,
)
from quant_research.signals.capital_cycle_features import (
    SnapshotVintage,
)
from quant_research.signals.capital_cycle_thresholds import (
    THRESHOLD_PROFILES,
)
from quant_research.signals.universe import (
    build_company_signal_series,
)


@dataclass(frozen=True)
class PipelineCompany:
    """Minimum company information needed by the pipeline."""

    id: int
    ticker: str
    cik: str
    currency: str


@dataclass(frozen=True)
class CompanyCounts:
    """Stored business-record counts for one company."""

    filings: int
    financial_facts: int
    fiscal_periods: int
    normalized_financials: int

    @property
    def total(self) -> int:
        """Return the total number of tracked records."""

        return (
            self.filings
            + self.financial_facts
            + self.fiscal_periods
            + self.normalized_financials
        )

    def inserted_since(
        self,
        previous: CompanyCounts,
    ) -> CompanyCounts:
        """Return positive count differences."""

        return CompanyCounts(
            filings=max(
                0,
                self.filings - previous.filings,
            ),
            financial_facts=max(
                0,
                self.financial_facts
                - previous.financial_facts,
            ),
            fiscal_periods=max(
                0,
                self.fiscal_periods
                - previous.fiscal_periods,
            ),
            normalized_financials=max(
                0,
                self.normalized_financials
                - previous.normalized_financials,
            ),
        )


@dataclass(frozen=True)
class PipelineRefreshResult:
    """Final aggregate result of one refresh run."""

    run_id: int
    status: str
    companies_total: int
    companies_succeeded: int
    companies_failed: int
    records_inserted: int


class PipelineStepError(RuntimeError):
    """Raised when an existing command-line pipeline step fails."""

    def __init__(
        self,
        label: str,
        command: Sequence[str],
        output_lines: Sequence[str],
        return_code: int,
    ) -> None:
        recent_output = "\n".join(
            output_lines[-20:]
        )

        message = (
            f"{label} failed with exit code "
            f"{return_code}.\n"
            f"Command: {shlex.join(command)}"
        )

        if recent_output:
            message += (
                "\nRecent output:\n"
                f"{recent_output}"
            )

        super().__init__(message)


def load_pipeline_companies(
    engine: Engine,
    requested_tickers: Sequence[str] | None,
) -> list[PipelineCompany]:
    """Load all companies or a requested ticker subset."""

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
                "At least one ticker must be supplied."
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

        stored_companies = list(
            session.scalars(statement)
        )

        by_ticker = {
            company.ticker: company
            for company in stored_companies
        }

        if canonical_tickers is not None:
            missing_tickers = [
                ticker
                for ticker in canonical_tickers
                if ticker not in by_ticker
            ]

            if missing_tickers:
                raise ValueError(
                    "Unknown company ticker(s): "
                    + ", ".join(missing_tickers)
                )

            ordered_companies = [
                by_ticker[ticker]
                for ticker in canonical_tickers
            ]
        else:
            ordered_companies = stored_companies

        if not ordered_companies:
            raise ValueError(
                "No stored companies were found."
            )

        result: list[PipelineCompany] = []

        for company in ordered_companies:
            if not company.cik:
                raise ValueError(
                    f"{company.ticker} has no CIK."
                )

            if not company.currency:
                raise ValueError(
                    f"{company.ticker} has no currency."
                )

            result.append(
                PipelineCompany(
                    id=company.id,
                    ticker=company.ticker,
                    cik=str(company.cik),
                    currency=company.currency,
                )
            )

        return result


def company_counts(
    engine: Engine,
    company_id: int,
) -> CompanyCounts:
    """Count persisted business records for a company."""

    with Session(engine) as session:
        filings = (
            session.scalar(
                select(func.count(Filing.id)).where(
                    Filing.company_id == company_id
                )
            )
            or 0
        )

        financial_facts = (
            session.scalar(
                select(
                    func.count(FinancialFact.id)
                ).where(
                    FinancialFact.company_id
                    == company_id
                )
            )
            or 0
        )

        fiscal_periods = (
            session.scalar(
                select(
                    func.count(FiscalPeriod.id)
                ).where(
                    FiscalPeriod.company_id
                    == company_id
                )
            )
            or 0
        )

        normalized_financials = (
            session.scalar(
                select(
                    func.count(
                        NormalizedFinancial.id
                    )
                ).where(
                    NormalizedFinancial.company_id
                    == company_id
                )
            )
            or 0
        )

        return CompanyCounts(
            filings=filings,
            financial_facts=financial_facts,
            fiscal_periods=fiscal_periods,
            normalized_financials=(
                normalized_financials
            ),
        )


def create_pipeline_run(
    engine: Engine,
    companies_total: int,
) -> int:
    """Create the initial running record."""

    with Session(engine) as session:
        pipeline_run = PipelineRun(
            run_type="refresh",
            status="running",
            companies_total=companies_total,
            companies_succeeded=0,
            companies_failed=0,
            records_inserted=0,
        )

        session.add(pipeline_run)
        session.commit()
        session.refresh(pipeline_run)

        return pipeline_run.id


def finish_pipeline_run(
    engine: Engine,
    run_id: int,
    status: str,
    companies_succeeded: int,
    companies_failed: int,
    records_inserted: int,
    errors: Sequence[str],
) -> None:
    """Persist the final run status and aggregates."""

    with Session(engine) as session:
        pipeline_run = session.get(
            PipelineRun,
            run_id,
        )

        if pipeline_run is None:
            raise RuntimeError(
                f"Pipeline run {run_id} was not found."
            )

        pipeline_run.status = status
        pipeline_run.finished_at = datetime.now(
            UTC
        )
        pipeline_run.companies_succeeded = (
            companies_succeeded
        )
        pipeline_run.companies_failed = (
            companies_failed
        )
        pipeline_run.records_inserted = (
            records_inserted
        )

        error_message = "\n\n".join(errors)

        pipeline_run.error_message = (
            error_message[:10_000]
            if error_message
            else None
        )

        session.commit()


def run_command_step(
    label: str,
    command: Sequence[str],
) -> None:
    """Run one existing CLI module and stream output."""

    print()
    print(f"[{label}]")
    print(f"$ {shlex.join(command)}")

    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    if process.stdout is None:
        raise RuntimeError(
            f"{label} did not expose stdout."
        )

    output_lines: list[str] = []

    for raw_line in process.stdout:
        line = raw_line.rstrip()
        output_lines.append(line)
        print(line)

    return_code = process.wait()

    if return_code != 0:
        raise PipelineStepError(
            label=label,
            command=command,
            output_lines=output_lines,
            return_code=return_code,
        )


def refresh_company_data(
    company: PipelineCompany,
) -> None:
    """Execute all persistent-data refresh steps."""

    python = sys.executable

    run_command_step(
        label=f"{company.ticker}: SEC filings",
        command=[
            python,
            "-m",
            "quant_research.data.sec_ingestion",
            "--ticker",
            company.ticker,
            "--cik",
            company.cik,
            "--currency",
            company.currency,
        ],
    )

    run_command_step(
        label=f"{company.ticker}: SEC facts",
        command=[
            python,
            "-m",
            "quant_research.data.sec_facts_ingestion",
            "--ticker",
            company.ticker,
        ],
    )

    run_command_step(
        label=f"{company.ticker}: normalization",
        command=[
            python,
            "-m",
            "quant_research.normalization",
            "--ticker",
            company.ticker,
            "--all",
        ],
    )


def validate_company_signals(
    engine: Engine,
    company_id: int,
    ticker: str,
) -> None:
    """Verify that the refreshed data produces signals."""

    with Session(engine) as session:
        company = session.get(
            Company,
            company_id,
        )

        if company is None:
            raise RuntimeError(
                f"{ticker} disappeared from the database."
            )

        signal_series = build_company_signal_series(
            session=session,
            company=company,
            vintage=SnapshotVintage("latest"),
            as_of=None,
            thresholds=(
                THRESHOLD_PROFILES["baseline"]
            ),
            confirmation_hits=2,
            confirmation_window=3,
        )

        signal_count = len(
            signal_series.confirmed_signals
        )

        if signal_count == 0:
            raise RuntimeError(
                f"{ticker} produced no confirmed "
                "capital-cycle signals."
            )

        print()
        print(
            f"[{ticker}: signal validation]"
        )
        print(
            f"{signal_count} confirmed periods "
            "successfully calculated."
        )


def determine_run_status(
    companies_succeeded: int,
    companies_failed: int,
) -> str:
    """Resolve the aggregate pipeline status."""

    if companies_failed == 0:
        return "succeeded"

    if companies_succeeded == 0:
        return "failed"

    return "partial"


def refresh_companies(
    requested_tickers: Sequence[str] | None,
    validate_signals: bool = True,
) -> PipelineRefreshResult:
    """Refresh all requested companies and track the run."""

    engine = create_database_engine()

    companies = load_pipeline_companies(
        engine=engine,
        requested_tickers=requested_tickers,
    )

    run_id = create_pipeline_run(
        engine=engine,
        companies_total=len(companies),
    )

    companies_succeeded = 0
    companies_failed = 0
    records_inserted = 0
    errors: list[str] = []

    print(
        f"Pipeline run {run_id} started for "
        f"{len(companies)} companies."
    )

    try:
        for position, company in enumerate(
            companies,
            start=1,
        ):
            print()
            print("=" * 72)
            print(
                f"{company.ticker} "
                f"({position}/{len(companies)})"
            )
            print("=" * 72)

            before = company_counts(
                engine=engine,
                company_id=company.id,
            )

            company_error: Exception | None = None

            try:
                refresh_company_data(company)

                if validate_signals:
                    validate_company_signals(
                        engine=engine,
                        company_id=company.id,
                        ticker=company.ticker,
                    )

            # Deliberate company-level isolation: record the error
            # and continue refreshing the remaining companies.
            except Exception as error:  # noqa: BLE001
                company_error = error

            after = company_counts(
                engine=engine,
                company_id=company.id,
            )

            inserted = after.inserted_since(before)

            records_inserted += inserted.total

            print()
            print(
                f"[{company.ticker}: inserted records]"
            )
            print(
                f"Filings: {inserted.filings}"
            )
            print(
                "Financial facts: "
                f"{inserted.financial_facts}"
            )
            print(
                "Fiscal periods: "
                f"{inserted.fiscal_periods}"
            )
            print(
                "Normalized financials: "
                f"{inserted.normalized_financials}"
            )
            print(f"Total: {inserted.total}")

            if company_error is None:
                companies_succeeded += 1
                print(
                    f"{company.ticker}: succeeded."
                )
            else:
                companies_failed += 1

                error_text = (
                    f"{company.ticker}: "
                    f"{company_error}"
                )

                errors.append(error_text)

                print(
                    f"{company.ticker}: failed."
                )
                print(error_text)

        status = determine_run_status(
            companies_succeeded=(
                companies_succeeded
            ),
            companies_failed=companies_failed,
        )

        finish_pipeline_run(
            engine=engine,
            run_id=run_id,
            status=status,
            companies_succeeded=(
                companies_succeeded
            ),
            companies_failed=companies_failed,
            records_inserted=records_inserted,
            errors=errors,
        )

    except BaseException as fatal_error:
        errors.append(
            "Fatal pipeline error: "
            f"{fatal_error}"
        )

        finish_pipeline_run(
            engine=engine,
            run_id=run_id,
            status="failed",
            companies_succeeded=(
                companies_succeeded
            ),
            companies_failed=(
                len(companies)
                - companies_succeeded
            ),
            records_inserted=records_inserted,
            errors=errors,
        )

        raise

    print()
    print("=" * 72)
    print(f"Pipeline run {run_id} finished.")
    print(f"Status: {status}")
    print(
        "Companies succeeded: "
        f"{companies_succeeded}"
    )
    print(
        f"Companies failed: {companies_failed}"
    )
    print(
        f"Business records inserted: "
        f"{records_inserted}"
    )
    print("=" * 72)

    return PipelineRefreshResult(
        run_id=run_id,
        status=status,
        companies_total=len(companies),
        companies_succeeded=(
            companies_succeeded
        ),
        companies_failed=companies_failed,
        records_inserted=records_inserted,
    )
