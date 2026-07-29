from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.connection import create_database_engine
from quant_research.database.models import Company
from quant_research.normalization.revenue import normalize_revenue


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

        try:
            inserted, skipped = normalize_revenue(
                session,
                company,
            )

            session.commit()

        except Exception:
            session.rollback()
            raise

    print(
        f"GOOGL revenue normalization: "
        f"{inserted} inserted, "
        f"{skipped} already existed."
    )


if __name__ == "__main__":
    main()
