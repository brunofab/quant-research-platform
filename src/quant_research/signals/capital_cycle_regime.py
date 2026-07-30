from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from quant_research.signals.capital_cycle_features import (
    CapitalCycleFeatureSnapshot,
)

ZERO = Decimal(0)


class CapitalCycleRegime(str, Enum):
    """High-level state of a company's capital cycle."""

    EXPANSION = "EXPANSION"
    TRANSITION = "TRANSITION"
    HARVEST = "HARVEST"
    REACCELERATION = "REACCELERATION"
    MIXED = "MIXED"


@dataclass(frozen=True)
class CapitalCycleSignal:
    """One classified capital-cycle feature snapshot."""

    snapshot: CapitalCycleFeatureSnapshot
    regime: CapitalCycleRegime

    investment_pressure_active: bool
    cashflow_pressure_active: bool

    investment_accelerating: bool
    investment_easing: bool

    cashflow_worsening: bool
    cashflow_improving: bool


def previous_fiscal_period_key(
    fiscal_year: int,
    fiscal_quarter: int,
) -> tuple[int, int]:
    """Return the immediately preceding fiscal quarter."""

    if fiscal_quarter == 1:
        return (
            fiscal_year - 1,
            4,
        )

    return (
        fiscal_year,
        fiscal_quarter - 1,
    )


def classify_capital_cycle_snapshot(
    snapshot: CapitalCycleFeatureSnapshot,
    previous_signal: CapitalCycleSignal | None,
) -> CapitalCycleSignal:
    """Classify one capital-cycle feature snapshot."""

    investment_pressure_active = (
        snapshot.capex_growth_gap > ZERO
        and snapshot.capex_intensity_yoy_delta > ZERO
    )

    cashflow_pressure_active = (
        snapshot.fcf_margin_yoy_delta < ZERO
    )

    investment_accelerating = (
        snapshot.capex_growth_gap_qoq_delta > ZERO
        and snapshot.capex_intensity_yoy_delta_qoq_delta
        > ZERO
    )

    investment_easing = (
        snapshot.capex_growth_gap_qoq_delta < ZERO
        and snapshot.capex_intensity_yoy_delta_qoq_delta
        < ZERO
    )

    cashflow_worsening = (
        snapshot.fcf_margin_yoy_delta_qoq_delta < ZERO
    )

    cashflow_improving = (
        snapshot.fcf_margin_yoy_delta_qoq_delta > ZERO
    )

    harvest_conditions = (
        snapshot.capex_growth_gap <= ZERO
        and snapshot.capex_intensity_yoy_delta <= ZERO
        and snapshot.fcf_margin_yoy_delta >= ZERO
        and not investment_accelerating
        and not cashflow_worsening
    )

    previous_period_was_easing = (
        previous_signal is not None
        and (
            previous_signal.regime
            in {
                CapitalCycleRegime.TRANSITION,
                CapitalCycleRegime.HARVEST,
            }
            or previous_signal.investment_easing
            or previous_signal.cashflow_improving
        )
    )

    reacceleration_conditions = (
        investment_pressure_active
        and investment_accelerating
        and (
            cashflow_pressure_active
            or cashflow_worsening
        )
        and previous_period_was_easing
    )

    transition_conditions = (
        investment_pressure_active
        and (
            investment_easing
            or cashflow_improving
        )
    )

    expansion_conditions = (
        investment_pressure_active
        and cashflow_pressure_active
    )

    if harvest_conditions:
        regime = CapitalCycleRegime.HARVEST

    elif reacceleration_conditions:
        regime = CapitalCycleRegime.REACCELERATION

    elif transition_conditions:
        regime = CapitalCycleRegime.TRANSITION

    elif expansion_conditions:
        regime = CapitalCycleRegime.EXPANSION

    else:
        regime = CapitalCycleRegime.MIXED

    return CapitalCycleSignal(
        snapshot=snapshot,
        regime=regime,
        investment_pressure_active=(
            investment_pressure_active
        ),
        cashflow_pressure_active=(
            cashflow_pressure_active
        ),
        investment_accelerating=(
            investment_accelerating
        ),
        investment_easing=investment_easing,
        cashflow_worsening=cashflow_worsening,
        cashflow_improving=cashflow_improving,
    )


def classify_capital_cycle_snapshots(
    snapshots: list[CapitalCycleFeatureSnapshot],
) -> list[CapitalCycleSignal]:
    """Classify a chronological sequence of feature snapshots."""

    ordered_snapshots = sorted(
        snapshots,
        key=lambda snapshot: (
            snapshot.fiscal_year,
            snapshot.fiscal_quarter,
        ),
    )

    signals: list[CapitalCycleSignal] = []

    signals_by_period: dict[
        tuple[int, int],
        CapitalCycleSignal,
    ] = {}

    for snapshot in ordered_snapshots:
        previous_key = previous_fiscal_period_key(
            snapshot.fiscal_year,
            snapshot.fiscal_quarter,
        )

        previous_signal = signals_by_period.get(
            previous_key
        )

        signal = classify_capital_cycle_snapshot(
            snapshot=snapshot,
            previous_signal=previous_signal,
        )

        period_key = (
            snapshot.fiscal_year,
            snapshot.fiscal_quarter,
        )

        signals_by_period[period_key] = signal
        signals.append(signal)

    return signals
