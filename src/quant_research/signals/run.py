import argparse
import json
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from quant_research.database.connection import (
    create_database_engine,
)
from quant_research.signals.capital_cycle_confirmation import (
    ConfirmedCapitalCycleSignal,
)
from quant_research.signals.capital_cycle_diagnostics import (
    CapitalCycleDiagnostics,
    build_capital_cycle_diagnostics,
)
from quant_research.signals.capital_cycle_features import (
    SnapshotVintage,
)
from quant_research.signals.capital_cycle_regime import (
    CapitalCycleRegime,
    CapitalCycleSignal,
)
from quant_research.signals.capital_cycle_thresholds import (
    THRESHOLD_PROFILES,
    CapitalCycleThresholds,
)
from quant_research.signals.universe import (
    CompanySignalSeries,
    build_universe_overview,
    build_universe_series,
    deduplicate_tickers,
    resolve_universe_tickers,
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

    return f"{value * Decimal(100):.1f}"


def resolve_threshold_profiles(
    classifier: str,
) -> list[CapitalCycleThresholds]:
    """Resolve the requested classifier profiles."""

    if classifier == "both":
        return [
            THRESHOLD_PROFILES["baseline"],
            THRESHOLD_PROFILES["calibrated"],
        ]

    return [
        THRESHOLD_PROFILES[classifier]
    ]


def print_signals(
    ticker: str,
    signals: list[CapitalCycleSignal],
    requested_as_of: date | None,
    vintage: SnapshotVintage,
    thresholds: CapitalCycleThresholds,
) -> None:
    """Print classified capital-cycle snapshots."""

    print()

    if requested_as_of is None:
        print(
            f"{ticker} capital-cycle regimes"
        )
    else:
        print(
            f"{ticker} capital-cycle regimes "
            f"as of {requested_as_of}"
        )

    print(
        f"Classifier: {thresholds.name.upper()}"
    )

    print(
        f"Snapshot vintage: {vintage.value.upper()}"
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

    print("-" * 116)

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
    thresholds: CapitalCycleThresholds,
) -> None:
    """Print component states and explanations."""

    if not signals:
        return

    print()
    print(
        "Component diagnostics "
        f"({thresholds.name.upper()})"
    )
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
    vintage: SnapshotVintage,
    thresholds: CapitalCycleThresholds,
) -> None:
    """Print historical regime and feature diagnostics."""

    print()
    print("Historical calibration diagnostics")
    print("-" * 72)

    print(
        f"Classifier: {thresholds.name.upper()}"
    )

    print(
        f"Snapshot vintage: {vintage.value.upper()}"
    )

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


def print_confirmed_signals(
    ticker: str,
    signals: list[ConfirmedCapitalCycleSignal],
    requested_as_of: date | None,
    vintage: SnapshotVintage,
    thresholds: CapitalCycleThresholds,
) -> None:
    """Print raw and confirmed regimes side by side."""

    print()

    if requested_as_of is None:
        print(
            f"{ticker} confirmed capital-cycle regimes"
        )
    else:
        print(
            f"{ticker} confirmed capital-cycle regimes "
            f"as of {requested_as_of}"
        )

    print(
        f"Classifier: {thresholds.name.upper()}"
    )

    print(
        f"Snapshot vintage: {vintage.value.upper()}"
    )

    if not signals:
        print(
            "No confirmed capital-cycle signals are available."
        )
        return

    print()

    print(
        f"{'Fiscal period':<14}"
        f"{'As of':<12}"
        f"{'Raw':<16}"
        f"{'Confirmed':<16}"
        f"{'Candidate':<16}"
        f"{'Progress':>10}"
        f"{'Changed':>10}"
    )

    print("-" * 94)

    for signal in signals:
        snapshot = signal.snapshot

        fiscal_period = (
            f"FY{snapshot.fiscal_year} "
            f"Q{snapshot.fiscal_quarter}"
        )

        candidate = (
            signal.candidate_regime.value
            if signal.candidate_regime is not None
            else "-"
        )

        progress = (
            f"{signal.candidate_hits}/"
            f"{signal.confirmation_required}"
            if signal.confirmation_pending
            else "-"
        )

        changed = (
            "YES"
            if signal.changed_this_period
            else "NO"
        )

        print(
            f"{fiscal_period:<14}"
            f"{snapshot.as_of.isoformat():<12}"
            f"{signal.raw_regime.value:<16}"
            f"{signal.regime.value:<16}"
            f"{candidate:<16}"
            f"{progress:>10}"
            f"{changed:>10}"
        )

def print_confirmation_comparison(
    raw_diagnostics: CapitalCycleDiagnostics,
    confirmed_diagnostics: CapitalCycleDiagnostics,
    vintage: SnapshotVintage,
    thresholds: CapitalCycleThresholds,
    confirmation_required: int,
    confirmation_window: int,
) -> None:
    """Compare raw and stabilized regime diagnostics."""

    print()
    print("Raw versus confirmed regime diagnostics")
    print("-" * 72)

    print(
        f"Classifier: {thresholds.name.upper()}"
    )

    print(
        f"Snapshot vintage: {vintage.value.upper()}"
    )

    print(
        "Confirmation rule: "
        f"{confirmation_required} hits within a rolling "
        f"{confirmation_window}-quarter window"
    )

    print()

    print(
        f"{'Mode':<14}"
        f"{'Periods':>10}"
        f"{'Switches':>11}"
        f"{'Avg run':>12}"
        f"{'Longest':>11}"
        f"{'Mixed':>11}"
    )

    print("-" * 70)

    for label, diagnostics in (
        ("RAW", raw_diagnostics),
        ("CONFIRMED", confirmed_diagnostics),
    ):
        longest_length = (
            diagnostics.longest_run.length
            if diagnostics.longest_run is not None
            else 0
        )

        mixed_share = (
            diagnostics.regime_shares[
                CapitalCycleRegime.MIXED
            ]
            * Decimal(100)
        )

        print(
            f"{label:<14}"
            f"{diagnostics.total_periods:>10}"
            f"{diagnostics.regime_switches:>11}"
            f"{diagnostics.average_run_length:>12.2f}"
            f"{longest_length:>11}"
            f"{mixed_share:>10.1f}%"
        )


def print_universe_overview(
    series: list[CompanySignalSeries],
    requested_as_of: date | None,
    vintage: SnapshotVintage,
    thresholds: CapitalCycleThresholds,
) -> None:
    """Print the latest dashboard-style signal for each company."""

    print()

    if requested_as_of is None:
        print("Capital-cycle universe overview")
    else:
        print(
            "Capital-cycle universe overview "
            f"as of {requested_as_of}"
        )

    print(
        f"Classifier: {thresholds.name.upper()}"
    )

    print(
        f"Snapshot vintage: {vintage.value.upper()}"
    )

    print(
        "All feature values are percentage points."
    )

    print()

    print(
        f"{'Ticker':<8}"
        f"{'Fiscal':<10}"
        f"{'As of':<12}"
        f"{'Confirmed':<16}"
        f"{'Raw':<16}"
        f"{'Candidate':<16}"
        f"{'Progress':>10}"
        f"{'Gap':>8}"
        f"{'Int YoY':>10}"
        f"{'FCF YoY':>10}"
        f"{'Gap QoQ':>10}"
        f"{'Int QoQ':>10}"
        f"{'FCF QoQ':>10}"
    )

    print("-" * 146)

    for company_series in series:
        if not company_series.confirmed_signals:
            print(
                f"{company_series.ticker:<8}"
                f"{'-':<10}"
                f"{'-':<12}"
                f"{'NO DATA':<16}"
                f"{'-':<16}"
                f"{'-':<16}"
                f"{'-':>10}"
                f"{'-':>8}"
                f"{'-':>10}"
                f"{'-':>10}"
                f"{'-':>10}"
                f"{'-':>10}"
                f"{'-':>10}"
            )
            continue

        signal = company_series.confirmed_signals[-1]
        snapshot = signal.snapshot

        fiscal_period = (
            f"FY{snapshot.fiscal_year} "
            f"Q{snapshot.fiscal_quarter}"
        )

        candidate = (
            signal.candidate_regime.value
            if signal.candidate_regime is not None
            else "-"
        )

        progress = (
            f"{signal.candidate_hits}/"
            f"{signal.confirmation_required}"
            if signal.confirmation_pending
            else "-"
        )

        print(
            f"{company_series.ticker:<8}"
            f"{fiscal_period:<10}"
            f"{snapshot.as_of.isoformat():<12}"
            f"{signal.regime.value:<16}"
            f"{signal.raw_regime.value:<16}"
            f"{candidate:<16}"
            f"{progress:>10}"
            f"{format_percentage_points(snapshot.capex_growth_gap):>8}"
            f"{format_percentage_points(snapshot.capex_intensity_yoy_delta):>10}"
            f"{format_percentage_points(snapshot.fcf_margin_yoy_delta):>10}"
            f"{format_percentage_points(snapshot.capex_growth_gap_qoq_delta):>10}"
            f"{format_percentage_points(snapshot.capex_intensity_yoy_delta_qoq_delta):>10}"
            f"{format_percentage_points(snapshot.fcf_margin_yoy_delta_qoq_delta):>10}"
        )


def requested_tickers_from_args(
    args: argparse.Namespace,
) -> list[str] | None:
    """Translate CLI company-selection arguments for the service layer."""

    if args.ticker is not None:
        return [args.ticker]

    if args.tickers is not None:
        return deduplicate_tickers(
            args.tickers
        )

    if args.all_companies:
        return None

    raise ValueError(
        "No company selection was supplied."
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Build point-in-time capital-cycle regimes."
        )
    )

    target_group = parser.add_mutually_exclusive_group(
        required=True
    )

    target_group.add_argument(
        "--ticker",
        help="Single company ticker, for example GOOGL.",
    )

    target_group.add_argument(
        "--tickers",
        nargs="+",
        help=(
            "Multiple company tickers, for example "
            "GOOGL MSFT META AMZN."
        ),
    )

    target_group.add_argument(
        "--all-companies",
        action="store_true",
        help=(
            "Run all companies currently stored in the database."
        ),
    )

    parser.add_argument(
        "--overview",
        action="store_true",
        help=(
            "Show one latest dashboard-style row per company."
        ),
    )

    parser.add_argument(
        "--format",
        choices=(
            "table",
            "json",
        ),
        default="table",
        help=(
            "Output format for overview mode. "
            "Default: table."
        ),
    )

    parser.add_argument(
        "--latest",
        type=positive_integer,
        default=8,
        help=(
            "Number of latest fiscal periods to show in "
            "detail mode. Default: 8."
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

    parser.add_argument(
        "--diagnostics-only",
        action="store_true",
        help=(
            "Only show historical calibration diagnostics."
        ),
    )

    parser.add_argument(
        "--vintage",
        choices=tuple(
            vintage.value
            for vintage in SnapshotVintage
        ),
        default=SnapshotVintage.LATEST.value,
        help=(
            "Snapshot version selected per fiscal period. "
            "Default: latest."
        ),
    )

    parser.add_argument(
        "--classifier",
        choices=(
            "baseline",
            "calibrated",
            "both",
        ),
        default="both",
        help=(
            "Classifier profile to run. Default: both."
        ),
    )

    parser.add_argument(
        "--confirmation-hits",
        "--confirmation-quarters",
        dest="confirmation_hits",
        type=positive_integer,
        default=2,
        help=(
            "Raw occurrences required to confirm a regime "
            "inside the rolling window. Default: 2."
        ),
    )

    parser.add_argument(
        "--confirmation-window",
        type=positive_integer,
        default=3,
        help=(
            "Number of consecutive fiscal quarters in the "
            "rolling confirmation window. Default: 3."
        ),
    )

    parser.add_argument(
        "--regime-view",
        choices=(
            "raw",
            "confirmed",
            "both",
        ),
        default="both",
        help=(
            "Regime output to show in detail mode. Default: both."
        ),
    )

    args = parser.parse_args()

    if args.confirmation_hits > args.confirmation_window:
        parser.error(
            "--confirmation-hits cannot exceed "
            "--confirmation-window."
        )

    if args.overview and (
        args.details
        or args.diagnostics
        or args.diagnostics_only
    ):
        parser.error(
            "--overview cannot be combined with "
            "--details, --diagnostics, or "
            "--diagnostics-only."
        )

    if args.format == "json" and not args.overview:
        parser.error(
            "--format json currently requires --overview."
        )

    return args


def print_company_detail(
    series: CompanySignalSeries,
    args: argparse.Namespace,
    vintage: SnapshotVintage,
    thresholds: CapitalCycleThresholds,
) -> None:
    """Print the existing detailed output for one company."""

    selected_raw_signals = series.raw_signals[
        -args.latest:
    ]

    selected_confirmed_signals = (
        series.confirmed_signals[
            -args.latest:
        ]
    )

    raw_diagnostics = (
        build_capital_cycle_diagnostics(
            signals=series.raw_signals
        )
    )

    confirmed_diagnostics = (
        build_capital_cycle_diagnostics(
            signals=series.confirmed_signals
        )
    )

    if not args.diagnostics_only:
        if args.regime_view in {
            "raw",
            "both",
        }:
            print_signals(
                ticker=series.ticker,
                signals=selected_raw_signals,
                requested_as_of=args.as_of,
                vintage=vintage,
                thresholds=thresholds,
            )

        if args.details:
            print_signal_details(
                signals=selected_raw_signals,
                thresholds=thresholds,
            )

        if args.regime_view in {
            "confirmed",
            "both",
        }:
            print_confirmed_signals(
                ticker=series.ticker,
                signals=selected_confirmed_signals,
                requested_as_of=args.as_of,
                vintage=vintage,
                thresholds=thresholds,
            )

    if args.diagnostics:
        print_diagnostics(
            diagnostics=raw_diagnostics,
            vintage=vintage,
            thresholds=thresholds,
        )

    if args.diagnostics or args.diagnostics_only:
        print_confirmation_comparison(
            raw_diagnostics=raw_diagnostics,
            confirmed_diagnostics=(
                confirmed_diagnostics
            ),
            vintage=vintage,
            thresholds=thresholds,
            confirmation_required=(
                args.confirmation_hits
            ),
            confirmation_window=(
                args.confirmation_window
            ),
        )


def main() -> None:
    args = parse_args()

    vintage = SnapshotVintage(
        args.vintage
    )

    threshold_profiles = (
        resolve_threshold_profiles(
            args.classifier
        )
    )

    requested_tickers = (
        requested_tickers_from_args(
            args
        )
    )

    engine = create_database_engine()

    with Session(engine) as session:
        tickers = resolve_universe_tickers(
            session=session,
            requested_tickers=requested_tickers,
        )

        if args.overview and args.format == "json":
            payload = build_universe_overview(
                session=session,
                requested_tickers=tickers,
                vintage=vintage,
                as_of=args.as_of,
                threshold_profiles=threshold_profiles,
                confirmation_hits=(
                    args.confirmation_hits
                ),
                confirmation_window=(
                    args.confirmation_window
                ),
            )

            print(
                json.dumps(
                    payload,
                    indent=2,
                )
            )
            return

        for thresholds in threshold_profiles:
            company_series = build_universe_series(
                session=session,
                tickers=tickers,
                vintage=vintage,
                as_of=args.as_of,
                thresholds=thresholds,
                confirmation_hits=(
                    args.confirmation_hits
                ),
                confirmation_window=(
                    args.confirmation_window
                ),
            )

            if args.overview:
                print_universe_overview(
                    series=company_series,
                    requested_as_of=args.as_of,
                    vintage=vintage,
                    thresholds=thresholds,
                )
                continue

            for series in company_series:
                print_company_detail(
                    series=series,
                    args=args,
                    vintage=vintage,
                    thresholds=thresholds,
                )


if __name__ == "__main__":
    main()
