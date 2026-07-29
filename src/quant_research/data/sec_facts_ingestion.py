import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from quant_research.data.sec import SECClient
from quant_research.database.connection import create_database_engine
from quant_research.database.models import Company, FinancialFact

BATCH_SIZE = 1000


def parse_optional_date(value: str | None) -> date | None:
    """Convert an optional ISO date string into a Python date."""
    if not value:
        return None

    return date.fromisoformat(value)


def parse_decimal(value: Any) -> Decimal | None:
    """Convert a numeric SEC value to Decimal."""

    if value is None or isinstance(value, bool):
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def create_source_key(
    *,
    cik: str,
    taxonomy: str,
    concept: str,
    unit: str,
    value: Decimal,
    period_start: date | None,
    period_end: date,
    filed_at: date,
    accession_number: str | None,
    form: str | None,
    fiscal_year: int | None,
    fiscal_period: str | None,
    frame: str | None,
) -> str:
    """Create a deterministic SHA-256 identifier for one SEC fact."""

    identity = {
        "cik": cik,
        "taxonomy": taxonomy,
        "concept": concept,
        "unit": unit,
        "value": str(value.normalize()),
        "period_start": (
            period_start.isoformat()
            if period_start is not None
            else None
        ),
        "period_end": period_end.isoformat(),
        "filed_at": filed_at.isoformat(),
        "accession_number": accession_number,
        "form": form,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "frame": frame,
    }

    canonical_json = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()


def transform_company_facts(
    company: Company,
    company_facts: dict[str, Any],
) -> list[dict[str, Any]]:
    """Transform SEC CompanyFacts JSON into database rows."""

    rows: list[dict[str, Any]] = []

    taxonomies = company_facts.get("facts", {})

    for taxonomy, concepts in taxonomies.items():
        for concept, concept_data in concepts.items():
            units = concept_data.get("units", {})

            for unit, facts in units.items():
                for fact in facts:
                    value = parse_decimal(fact.get("val"))

                    if value is None:
                        continue

                    end_raw = fact.get("end")
                    filed_raw = fact.get("filed")

                    if not end_raw or not filed_raw:
                        continue

                    period_start = parse_optional_date(
                        fact.get("start")
                    )
                    period_end = date.fromisoformat(end_raw)
                    filed_at = date.fromisoformat(filed_raw)

                    accession_number = fact.get("accn")
                    form = fact.get("form")
                    fiscal_year = fact.get("fy")
                    fiscal_period = fact.get("fp")
                    frame = fact.get("frame")

                    source_key = create_source_key(
                        cik=company.cik,
                        taxonomy=taxonomy,
                        concept=concept,
                        unit=unit,
                        value=value,
                        period_start=period_start,
                        period_end=period_end,
                        filed_at=filed_at,
                        accession_number=accession_number,
                        form=form,
                        fiscal_year=fiscal_year,
                        fiscal_period=fiscal_period,
                        frame=frame,
                    )

                    rows.append(
                        {
                            "source_key": source_key,
                            "company_id": company.id,
                            "taxonomy": taxonomy,
                            "concept": concept,
                            "unit": unit,
                            "value": value,
                            "period_start": period_start,
                            "period_end": period_end,
                            "filed_at": filed_at,
                            "accession_number": accession_number,
                            "form": form,
                            "fiscal_year": fiscal_year,
                            "fiscal_period": fiscal_period,
                            "frame": frame,
                            "source": "SEC",
                        }
                    )

    return rows


def insert_fact_rows(
    session: Session,
    rows: list[dict[str, Any]],
) -> tuple[int, int]:
    """Insert facts in batches and ignore existing source keys."""

    inserted = 0

    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]

        statement = (
            insert(FinancialFact)
            .values(batch)
            .on_conflict_do_nothing(
                index_elements=["source_key"]
            )
            .returning(FinancialFact.source_key)
        )

        result = session.execute(statement)

        inserted += len(result.scalars().all())

    skipped = len(rows) - inserted

    return inserted, skipped


def ingest_company_facts(
    cik: str | int,
) -> None:
    """Download and persist SEC CompanyFacts for one company."""

    engine = create_database_engine()

    with Session(engine) as session:
        company = session.scalar(
            select(Company).where(
                Company.cik == str(cik).zfill(10)
            )
        )

        if company is None:
            raise ValueError(
                f"Company with CIK {cik} does not exist."
            )

        with SECClient() as sec:
            company_facts = sec.get_company_facts(cik)

        rows = transform_company_facts(
            company=company,
            company_facts=company_facts,
        )

        try:
            inserted, skipped = insert_fact_rows(
                session=session,
                rows=rows,
            )

            session.commit()

        except Exception:
            session.rollback()
            raise

    print(
        f"{company.ticker}: "
        f"{inserted} financial facts inserted, "
        f"{skipped} already existed."
    )


def main() -> None:
    ingest_company_facts("1652044")


if __name__ == "__main__":
    main()
