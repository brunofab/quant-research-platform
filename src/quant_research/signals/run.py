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
from quant_research.signals.capital_cycle_diagnostics import (
    CapitalCycleDiagnostics,
    build_capital_cycle_diagnostics,
)
from quant_research.signals.capital_cycle_features import (
    build_capital_cycle_feature_snapshots,
    load_capital_cycle_feature_observations,
    select_latest_snapshot_per_period,
)
from quant_research.signals.capital_cycle_regime import (
    CapitalCycleRegime,
    CapitalCycleSignal,
    classify_capital_cycle_snapshots,
)

FEATURE_LABELS = {
    "capex_growth_gap": "Growth gap",
    "capex_intensity_yoy_delta": "Intensity YoY",
    "fcf_margin_yoy_delta": "FCF margin YoY",
    "capex_growth_gap_qoq_delta": "Growth-gap QoQ",
    "capex_intensity_yoy_delta_qoq_delta": (
        "Intensity QoQ"
    ),
    "fcf_margin_yoy_delta_qoq_delta": "FCF QoQ",
}


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


def print_signals(
    ticker: str,
    signals: list[CapitalCycleSignal],
    requested_as_of: date | None,
) -> None:
    """Print classified capital-cycle snapshots."""

    print()

    if requested_as_of is None:
        print(
            f"{ticker} latest capital-cycle regimes"
        )
    else:
        print(
            f"{ticker} capital-cycle regimes "
            f"as of {requested_as_of}"
        )

    print(
        "All feature values are percentage points."
    )

    if not signals:
        print(
            "No complete capital-cycle signals are available."
        )
        return

    print()

    print(
        f"{'Fiscal period':<14}"
        f"{'As of':<12}"
        f"{'Regime':<16}"
        f"{'Gap':>8}"
        f"{'Intensity YoY':>15}"
        f"{'FCF margin YoY':>16}"
        f"{'Gap QoQ':>10}"
        f"{'Intensity QoQ':>15}"
        f"{'FCF QoQ':>10}"
    )

    print(
        "-" * 116
    )

    for signal in signals:
        snapshot = signal.snapshot

        fiscal_period = (
            f"FY{snapshot.fiscal_year} "
            f"Q{snapshot.fiscal_quarter}"
        )

        print(
            f"{fiscal_period:<14}"
            f"{snapshot.as_of.isoformat():<12}"
            f"{signal.regime.value:<16}"
            f"{format_percentage_points(snapshot.capex_growth_gap):>8}"
            f"{format_percentage_points(snapshot.capex_intensity_yoy_delta):>15}"
            f"{format_percentage_points(snapshot.fcf_margin_yoy_delta):>16}"
            f"{format_percentage_points(snapshot.capex_growth_gap_qoq_delta):>10}"
            f"{format_percentage_points(snapshot.capex_intensity_yoy_delta_qoq_delta):>15}"
            f"{format_percentage_points(snapshot.fcf_margin_yoy_delta_qoq_delta):>10}"
        )


def print_signal_details(
    signals: list[CapitalCycleSignal],
) -> None:
    """Print component states and classification explanations."""

    if not signals:
        return

    print()
    print("Component diagnostics")
    print("-" * 88)

    for signal in signals:
        snapshot = signal.snapshot

        fiscal_period = (
            f"FY{snapshot.fiscal_year} "
            f"Q{snapshot.fiscal_quarter}"
        )

        print(
            f"{fiscal_period} | "
            f"{signal.regime.value}"
        )

        print(
            "  "
            f"investment pressure: "
            f"{signal.investment_pressure.value}; "
            f"cashflow pressure: "
            f"{signal.cashflow_pressure.value}"
        )

        print(
            "  "
            f"investment momentum: "
            f"{signal.investment_momentum.value}; "
            f"cashflow momentum: "
            f"{signal.cashflow_momentum.value}"
        )

        print(
            f"  reason: "
            f"{signal.classification_reason}"
        )


def print_diagnostics(
    diagnostics: CapitalCycleDiagnostics,
) -> None:
    """Print historical regime and feature diagnostics."""

    print()
    print("Historical calibration diagnostics")
    print("-" * 72)

    if diagnostics.total_periods == 0:
        print(
            "No complete historical signals are available."
        )
        return

    first_period = diagnostics.first_period
    last_period = diagnostics.last_period

    if first_period is None or last_period is None:
        raise ValueError(
            "Non-empty diagnostics have no coverage periods."
        )

    print(
        "Coverage: "
        f"FY{first_period[0]} Q{first_period[1]} "
        "to "
        f"FY{last_period[0]} Q{last_period[1]}"
    )

    print(
        f"Complete periods: {diagnostics.total_periods}"
    )

    print(
        f"Regime switches: {diagnostics.regime_switches}"
    )

    print(
        "Average uninterrupted regime length: "
        f"{diagnostics.average_run_length:.2f} quarters"
    )

    if diagnostics.longest_run is not None:
        longest = diagnostics.longest_run

        print(
            "Longest run: "
            f"{longest.regime.value}, "
            f"FY{longest.start_fiscal_year} "
            f"Q{longest.start_fiscal_quarter} to "
            f"FY{longest.end_fiscal_year} "
            f"Q{longest.end_fiscal_quarter} "
            f"({longest.length} quarters)"
        )

    print()
    print("Regime distribution")
    print(
        f"{'Regime':<18}"
        f"{'Count':>8}"
        f"{'Share':>10}"
    )
    print("-" * 36)

    for regime in CapitalCycleRegime:
        count = diagnostics.regime_counts[
            regime
        ]

        share = (
            diagnostics.regime_shares[
                regime
            ]
            * Decimal(100)
        )

        print(
            f"{regime.value:<18}"
            f"{count:>8}"
            f"{share:>9.1f}%"
        )

    print()
    print("Observed consecutive-period transitions")
    print(
        f"{'From':<18}"
        f"{'To':<18}"
        f"{'Count':>8}"
    )
    print("-" * 44)

    ordered_transitions = sorted(
        diagnostics.transitions.items(),
        key=lambda item: (
            -item[1],
            item[0][0].value,
            item[0][1].value,
        ),
    )

    for (
        source,
        destination,
    ), count in ordered_transitions:
        print(
            f"{source.value:<18}"
            f"{destination.value:<18}"
            f"{count:>8}"
        )

    print()
    print("Historical feature distributions")
    print(
        "All values below are percentage points."
    )

    print(
        f"{'Feature':<22}"
        f"{'Min':>9}"
        f"{'P25':>9}"
        f"{'Median':>9}"
        f"{'P75':>9}"
        f"{'Max':>9}"
    )

    print("-" * 76)

    for feature_name, label in FEATURE_LABELS.items():
        distribution = (
            diagnostics.feature_distributions[
                feature_name
            ]
        )

        print(
            f"{label:<22}"
            f"{format_percentage_points(distribution.minimum):>9}"
            f"{format_percentage_points(distribution.p25):>9}"
            f"{format_percentage_points(distribution.median):>9}"
            f"{format_percentage_points(distribution.p75):>9}"
            f"{format_percentage_points(distribution.maximum):>9}"
        )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Build point-in-time capital-cycle regimes."
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

    parser.add_argument(
        "--details",
        action="store_true",
        help=(
            "Show component states and classification reasons."
        ),
    )

    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help=(
            "Show historical regime and feature diagnostics."
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

        # Keep all historical periods available for classification.
        # Reacceleration depends on the immediately preceding period.
        latest_per_period = (
            select_latest_snapshot_per_period(
                snapshots=snapshots,
                as_of=args.as_of,
                limit=None,
            )
        )

        signals = classify_capital_cycle_snapshots(
            snapshots=latest_per_period
        )

        selected_signals = signals[
            -args.latest:
        ]

        # Diagnostics use the full classified history rather than
        # only the periods selected through --latest.
        diagnostics = (
            build_capital_cycle_diagnostics(
                signals=signals
            )
        )

    print_signals(
        ticker=ticker,
        signals=selected_signals,
        requested_as_of=args.as_of,
    )

    if args.details:
        print_signal_details(
            signals=selected_signals
        )

    if args.diagnostics:
        print_diagnostics(
            diagnostics=diagnostics
        )


if __name__ == "__main__":
    main()