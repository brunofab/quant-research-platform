from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from quant_research.signals.capital_cycle_regime import (
    CapitalCycleRegime,
    CapitalCycleSignal,
    previous_fiscal_period_key,
)

FEATURE_NAMES = (
    "capex_growth_gap",
    "capex_intensity_yoy_delta",
    "fcf_margin_yoy_delta",
    "capex_growth_gap_qoq_delta",
    "capex_intensity_yoy_delta_qoq_delta",
    "fcf_margin_yoy_delta_qoq_delta",
)


@dataclass(frozen=True)
class FeatureDistribution:
    """Distribution summary for one continuous feature."""

    count: int
    minimum: Decimal
    p25: Decimal
    median: Decimal
    p75: Decimal
    maximum: Decimal

    def to_payload(self) -> dict[str, object]:
        """Return a dashboard-friendly representation."""

        return {
            "count": self.count,
            "minimum": float(self.minimum),
            "p25": float(self.p25),
            "median": float(self.median),
            "p75": float(self.p75),
            "maximum": float(self.maximum),
        }


@dataclass(frozen=True)
class RegimeRun:
    """One uninterrupted sequence of the same regime."""

    regime: CapitalCycleRegime
    start_fiscal_year: int
    start_fiscal_quarter: int
    end_fiscal_year: int
    end_fiscal_quarter: int
    length: int

    def to_payload(self) -> dict[str, object]:
        """Return a dashboard-friendly representation."""

        return {
            "regime": self.regime.value,
            "start": {
                "fiscal_year": self.start_fiscal_year,
                "fiscal_quarter": self.start_fiscal_quarter,
            },
            "end": {
                "fiscal_year": self.end_fiscal_year,
                "fiscal_quarter": self.end_fiscal_quarter,
            },
            "length": self.length,
        }


@dataclass(frozen=True)
class CapitalCycleDiagnostics:
    """Historical diagnostics for one classified signal sequence."""

    total_periods: int
    first_period: tuple[int, int] | None
    last_period: tuple[int, int] | None

    regime_counts: dict[CapitalCycleRegime, int]
    regime_shares: dict[CapitalCycleRegime, Decimal]

    regime_switches: int
    runs: tuple[RegimeRun, ...]
    average_run_length: Decimal
    longest_run: RegimeRun | None

    transitions: dict[
        tuple[CapitalCycleRegime, CapitalCycleRegime],
        int,
    ]

    feature_distributions: dict[
        str,
        FeatureDistribution,
    ]

    def to_payload(self) -> dict[str, object]:
        """Return a dashboard- and API-friendly representation."""

        return {
            "total_periods": self.total_periods,
            "first_period": (
                {
                    "fiscal_year": self.first_period[0],
                    "fiscal_quarter": self.first_period[1],
                }
                if self.first_period is not None
                else None
            ),
            "last_period": (
                {
                    "fiscal_year": self.last_period[0],
                    "fiscal_quarter": self.last_period[1],
                }
                if self.last_period is not None
                else None
            ),
            "regime_counts": {
                regime.value: count
                for regime, count in self.regime_counts.items()
            },
            "regime_shares": {
                regime.value: float(share)
                for regime, share in self.regime_shares.items()
            },
            "regime_switches": self.regime_switches,
            "average_run_length": float(
                self.average_run_length
            ),
            "longest_run": (
                self.longest_run.to_payload()
                if self.longest_run is not None
                else None
            ),
            "transitions": [
                {
                    "from": source.value,
                    "to": destination.value,
                    "count": count,
                }
                for (
                    source,
                    destination,
                ), count in self.transitions.items()
            ],
            "feature_distributions": {
                feature: distribution.to_payload()
                for feature, distribution
                in self.feature_distributions.items()
            },
        }


def signal_period_key(
    signal: CapitalCycleSignal,
) -> tuple[int, int]:
    """Return the fiscal-period key for one signal."""

    return (
        signal.snapshot.fiscal_year,
        signal.snapshot.fiscal_quarter,
    )


def percentile(
    values: list[Decimal],
    fraction: Decimal,
) -> Decimal:
    """Calculate a linearly interpolated percentile."""

    if not values:
        raise ValueError(
            "Cannot calculate a percentile of an empty sequence."
        )

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (
        Decimal(len(ordered) - 1)
        * fraction
    )

    lower_index = int(position)
    upper_index = min(
        lower_index + 1,
        len(ordered) - 1,
    )

    interpolation_weight = (
        position
        - Decimal(lower_index)
    )

    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]

    return (
        lower_value
        + (
            upper_value
            - lower_value
        )
        * interpolation_weight
    )


def build_feature_distribution(
    values: list[Decimal],
) -> FeatureDistribution:
    """Build a distribution summary for one feature."""

    ordered = sorted(values)

    if not ordered:
        raise ValueError(
            "Cannot summarize an empty feature sequence."
        )

    return FeatureDistribution(
        count=len(ordered),
        minimum=ordered[0],
        p25=percentile(
            ordered,
            Decimal("0.25"),
        ),
        median=percentile(
            ordered,
            Decimal("0.50"),
        ),
        p75=percentile(
            ordered,
            Decimal("0.75"),
        ),
        maximum=ordered[-1],
    )


def build_regime_runs(
    signals: list[CapitalCycleSignal],
) -> tuple[RegimeRun, ...]:
    """Build uninterrupted runs of identical regimes."""

    ordered = sorted(
        signals,
        key=signal_period_key,
    )

    if not ordered:
        return ()

    runs: list[RegimeRun] = []

    run_start = ordered[0]
    previous = ordered[0]
    run_length = 1

    for signal in ordered[1:]:
        is_consecutive = (
            previous_fiscal_period_key(
                signal.snapshot.fiscal_year,
                signal.snapshot.fiscal_quarter,
            )
            == signal_period_key(previous)
        )

        same_regime = (
            signal.regime
            is run_start.regime
        )

        if is_consecutive and same_regime:
            run_length += 1
            previous = signal
            continue

        runs.append(
            RegimeRun(
                regime=run_start.regime,
                start_fiscal_year=(
                    run_start.snapshot.fiscal_year
                ),
                start_fiscal_quarter=(
                    run_start.snapshot.fiscal_quarter
                ),
                end_fiscal_year=(
                    previous.snapshot.fiscal_year
                ),
                end_fiscal_quarter=(
                    previous.snapshot.fiscal_quarter
                ),
                length=run_length,
            )
        )

        run_start = signal
        previous = signal
        run_length = 1

    runs.append(
        RegimeRun(
            regime=run_start.regime,
            start_fiscal_year=(
                run_start.snapshot.fiscal_year
            ),
            start_fiscal_quarter=(
                run_start.snapshot.fiscal_quarter
            ),
            end_fiscal_year=(
                previous.snapshot.fiscal_year
            ),
            end_fiscal_quarter=(
                previous.snapshot.fiscal_quarter
            ),
            length=run_length,
        )
    )

    return tuple(runs)


def build_transition_counts(
    signals: list[CapitalCycleSignal],
) -> dict[
    tuple[CapitalCycleRegime, CapitalCycleRegime],
    int,
]:
    """Count transitions between consecutive fiscal periods."""

    ordered = sorted(
        signals,
        key=signal_period_key,
    )

    transitions: Counter[
        tuple[CapitalCycleRegime, CapitalCycleRegime]
    ] = Counter()

    for previous, current in pairwise(ordered):
        is_consecutive = (
            previous_fiscal_period_key(
                current.snapshot.fiscal_year,
                current.snapshot.fiscal_quarter,
            )
            == signal_period_key(previous)
        )

        if not is_consecutive:
            continue

        transitions[
            (
                previous.regime,
                current.regime,
            )
        ] += 1

    return dict(transitions)


def build_capital_cycle_diagnostics(
    signals: list[CapitalCycleSignal],
) -> CapitalCycleDiagnostics:
    """Build historical diagnostics for capital-cycle signals."""

    ordered = sorted(
        signals,
        key=signal_period_key,
    )

    total_periods = len(ordered)

    regime_counter = Counter(
        signal.regime
        for signal in ordered
    )

    regime_counts = {
        regime: regime_counter.get(
            regime,
            0,
        )
        for regime in CapitalCycleRegime
    }

    regime_shares = {
        regime: (
            Decimal(count)
            / Decimal(total_periods)
            if total_periods > 0
            else Decimal(0)
        )
        for regime, count
        in regime_counts.items()
    }

    runs = build_regime_runs(
        ordered
    )

    average_run_length = (
        Decimal(total_periods)
        / Decimal(len(runs))
        if runs
        else Decimal(0)
    )

    longest_run = (
        max(
            runs,
            key=lambda run: run.length,
        )
        if runs
        else None
    )

    transitions = build_transition_counts(
        ordered
    )

    regime_switches = sum(
        count
        for (
            source,
            destination,
        ), count in transitions.items()
        if source is not destination
    )

    feature_distributions = {
        feature_name: build_feature_distribution(
            [
                getattr(
                    signal.snapshot,
                    feature_name,
                )
                for signal in ordered
            ]
        )
        for feature_name in FEATURE_NAMES
    } if ordered else {}

    return CapitalCycleDiagnostics(
        total_periods=total_periods,
        first_period=(
            signal_period_key(ordered[0])
            if ordered
            else None
        ),
        last_period=(
            signal_period_key(ordered[-1])
            if ordered
            else None
        ),
        regime_counts=regime_counts,
        regime_shares=regime_shares,
        regime_switches=regime_switches,
        runs=runs,
        average_run_length=average_run_length,
        longest_run=longest_run,
        transitions=transitions,
        feature_distributions=feature_distributions,
    )