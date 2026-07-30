import argparse
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.connection import (
    create_database_engine,
)
from quant_research.database.models import Company
from quant_research.normalization.fiscal_period_resolver import (
    FiscalPeriodResolver,
)
from quant_research.signals.capital_cycle_features import (
    CapitalCycleFeatureSnapshot,
    build_capital_cycle_feature_snapshots,
    load_capital_cycle_feature_observations,
    select_latest_snapshot_per_period,
)


def parse_iso_date(value: str) -> date:
    """Parse an ISO date supplied through the command line."""

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Date must use YYYY-MM-DD format."
        ) from error


def positive_integer(value: str) -> int:
    """Parse a strictly positive integer."""

    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Value must be an integer."
        ) from error

    if parsed <= 0:
        raise argparse.ArgumentTypeError(
            "Value must be greater than zero."
        )

    return parsed


def format_percentage_points(
    value: Decimal,
) -> str:
    """Format a ratio value as percentage points."""

    percentage_points = (
        value
        * Decimal(100)
    )

    return f"{percentage_points:.1f}"


def print_snapshots(
    ticker: str,
    snapshots: list[CapitalCycleFeatureSnapshot],
    requested_as_of: date | None,
) -> None:
    """Print capital-cycle snapshots as a compact table."""

    print()

    if requested_as_of is None:
        print(
            f"{ticker} latest capital-cycle feature snapshots"
        )
    else:
        print(
            f"{ticker} capital-cycle feature snapshots "
            f"as of {requested_as_of}"
        )

    print(
        "All feature values are percentage points."
    )

    if not snapshots:
        print(
            "No complete feature snapshots are available."
        )
        return

    print()
    print(
        f"{'Fiscal period':<14}"
        f"{'As of':<12}"
        f"{'Gap':>9}"
        f"{'Intensity YoY':>16}"
        f"{'FCF margin YoY':>17}"
        f"{'Gap QoQ':>11}"
        f"{'Intensity QoQ':>16}"
        f"{'FCF QoQ':>11}"
    )

    print(
        "-" * 106
    )

    for snapshot in snapshots:
        fiscal_period = (
            f"FY{snapshot.fiscal_year} "
            f"Q{snapshot.fiscal_quarter}"
        )

        print(
            f"{fiscal_period:<14}"
            f"{snapshot.as_of.isoformat():<12}"
            f"{format_percentage_points(snapshot.capex_growth_gap):>9}"
            f"{format_percentage_points(snapshot.capex_intensity_yoy_delta):>16}"
            f"{format_percentage_points(snapshot.fcf_margin_yoy_delta):>17}"
            f"{format_percentage_points(snapshot.capex_growth_gap_qoq_delta):>11}"
            f"{format_percentage_points(snapshot.capex_intensity_yoy_delta_qoq_delta):>16}"
            f"{format_percentage_points(snapshot.fcf_margin_yoy_delta_qoq_delta):>11}"
        )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Build point-in-time capital-cycle feature snapshots."
        )
    )

    parser.add_argument(
        "--ticker",
        required=True,
        help="Company ticker, for example GOOGL or MSFT.",
    )

    parser.add_argument(
        "--latest",
        type=positive_integer,
        default=8,
        help=(
            "Number of latest fiscal periods to show. "
            "Default: 8."
        ),
    )

    parser.add_argument(
        "--as-of",
        type=parse_iso_date,
        default=None,
        help=(
            "Historical information cutoff in YYYY-MM-DD format."
        ),
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

        resolver = FiscalPeriodResolver(
            session=session,
            company_id=company.id,
        )

        observations = (
            load_capital_cycle_feature_observations(
                session=session,
                company_id=company.id,
            )
        )

        snapshots = (
            build_capital_cycle_feature_snapshots(
                observations=observations,
                resolver=resolver,
            )
        )

        selected = (
            select_latest_snapshot_per_period(
                snapshots=snapshots,
                as_of=args.as_of,
                limit=args.latest,
            )
        )

    print_snapshots(
        ticker=ticker,
        snapshots=selected,
        requested_as_of=args.as_of,
    )


if __name__ == "__main__":
    main()
