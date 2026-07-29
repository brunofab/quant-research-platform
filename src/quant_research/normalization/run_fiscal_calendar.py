import argparse

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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Build the fiscal calendar for one company."
        )
    )

    parser.add_argument(
        "--ticker",
        required=True,
        help="Company ticker, for example GOOGL or MSFT.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ticker = args.ticker.upper()

    engine = create_database_engine()

    with Session(engine) as session:
        company = session.scalar(
            select(Company).where(
                Company.ticker == ticker
            )
        )

        if company is None:
            raise ValueError(
                f"{ticker} does not exist in companies."
            )

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