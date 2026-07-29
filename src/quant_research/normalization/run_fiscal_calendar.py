from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.connection import (
    create_database_engine,
)
from quant_research.database.models import Company
from quant_research.normalization.fiscal_calendar import (
    backfill_historical_fiscal_periods,
    sync_fiscal_periods,
)


def main() -> None:
    engine = create_database_engine()

    with Session(engine) as session:
        company = session.scalar(
            select(Company).where(
                Company.ticker == "GOOGL"
            )
        )

        if company is None:
            raise ValueError(
                "GOOGL does not exist in companies."
            )

        ticker = company.ticker

        try:
            authoritative_inserted, existing = (
                sync_fiscal_periods(
                    session,
                    company,
                )
            )

            historical_backfilled = (
                backfill_historical_fiscal_periods(
                    session,
                    company,
                )
            )

            session.commit()

        except Exception:
            session.rollback()
            raise

    print(
        f"{ticker} fiscal calendar: "
        f"{authoritative_inserted} authoritative inserted, "
        f"{historical_backfilled} historical backfilled, "
        f"{existing} already existed."
    )


if __name__ == "__main__":
    main()