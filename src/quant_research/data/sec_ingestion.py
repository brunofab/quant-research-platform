from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.data.sec import SECClient, format_cik
from quant_research.database.connection import create_database_engine
from quant_research.database.models import Company, Filing

PERIODIC_FORMS = {
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
}


def parse_optional_date(value: str | None) -> date | None:
    """Convert an ISO date string into a Python date."""

    if not value:
        return None

    return date.fromisoformat(value)


def get_exchange_for_ticker(
    submissions: dict,
    ticker: str,
) -> str | None:
    """Return the exchange corresponding to a ticker."""

    tickers = submissions.get("tickers", [])
    exchanges = submissions.get("exchanges", [])

    for index, sec_ticker in enumerate(tickers):
        if sec_ticker == ticker and index < len(exchanges):
            return exchanges[index]

    return None


def build_filing_url(
    cik: str,
    accession_number: str,
    primary_document: str | None,
) -> str | None:
    """Build the SEC archive URL for a filing's primary document."""

    if not primary_document:
        return None

    cik_without_leading_zeros = str(int(cik))
    accession_without_hyphens = accession_number.replace("-", "")

    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik_without_leading_zeros}/"
        f"{accession_without_hyphens}/"
        f"{primary_document}"
    )


def get_or_create_company(
    session: Session,
    submissions: dict,
    canonical_ticker: str,
    currency: str | None = None,
) -> Company:
    """Return an existing company or create it from SEC metadata."""

    cik = format_cik(submissions["cik"])

    company = session.scalar(
        select(Company).where(Company.cik == cik)
    )

    if company is not None:
        return company

    company = Company(
        ticker=canonical_ticker,
        cik=cik,
        name=submissions["name"],
        exchange=get_exchange_for_ticker(
            submissions,
            canonical_ticker,
        ),
        currency=currency,
    )

    session.add(company)

    # We need the database-generated company.id before inserting filings.
    session.flush()

    return company


def ingest_recent_filings(
    session: Session,
    company: Company,
    submissions: dict,
) -> tuple[int, int]:
    """Insert recent periodic SEC filings without creating duplicates."""

    recent = submissions["filings"]["recent"]

    inserted = 0
    skipped = 0

    accession_numbers = recent["accessionNumber"]

    for index, accession_number in enumerate(accession_numbers):
        form = recent["form"][index]

        if form not in PERIODIC_FORMS:
            continue

        existing_filing = session.scalar(
            select(Filing).where(
                Filing.accession_number == accession_number
            )
        )

        if existing_filing is not None:
            skipped += 1
            continue

        primary_document = recent["primaryDocument"][index] or None

        filing = Filing(
            company_id=company.id,
            accession_number=accession_number,
            form=form,
            filing_date=date.fromisoformat(
                recent["filingDate"][index]
            ),
            report_date=parse_optional_date(
                recent["reportDate"][index]
            ),
            primary_document=primary_document,
            source_url=build_filing_url(
                company.cik,
                accession_number,
                primary_document,
            ),
        )

        session.add(filing)
        inserted += 1

    return inserted, skipped


def ingest_company_filings(
    cik: str | int,
    canonical_ticker: str,
    currency: str | None = None,
) -> None:
    """Download and store a company's recent SEC filing metadata."""

    with SECClient() as sec:
        submissions = sec.get_submissions(cik)

    engine = create_database_engine()

    with Session(engine) as session:
        try:
            company = get_or_create_company(
                session=session,
                submissions=submissions,
                canonical_ticker=canonical_ticker,
                currency=currency,
            )

            inserted, skipped = ingest_recent_filings(
                session=session,
                company=company,
                submissions=submissions,
            )

            session.commit()

        except Exception:
            session.rollback()
            raise

    print(
        f"{canonical_ticker}: "
        f"{inserted} filings inserted, "
        f"{skipped} already existed."
    )


def main() -> None:
    ingest_company_filings(
        cik="1652044",
        canonical_ticker="GOOGL",
        currency="USD",
    )


if __name__ == "__main__":
    main()
