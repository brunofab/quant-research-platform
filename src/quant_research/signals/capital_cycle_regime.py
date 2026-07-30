from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from quant_research.signals.capital_cycle_features import (
    CapitalCycleFeatureSnapshot,
)

ZERO = Decimal(0)
PERCENT = Decimal(100)


class CapitalCycleRegime(str, Enum):
    """High-level state of a company's capital cycle."""

    EXPANSION = "EXPANSION"
    TRANSITION = "TRANSITION"
    HARVEST = "HARVEST"
    REACCELERATION = "REACCELERATION"
    MIXED = "MIXED"


class PressureState(str, Enum):
    """Whether one type of pressure is currently active."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class InvestmentMomentumState(str, Enum):
    """Direction of the investment-pressure indicators."""

    ACCELERATING = "ACCELERATING"
    EASING = "EASING"
    MIXED = "MIXED"
    FLAT = "FLAT"


class CashflowMomentumState(str, Enum):
    """Direction of the cashflow-pressure indicator."""

    IMPROVING = "IMPROVING"
    WORSENING = "WORSENING"
    FLAT = "FLAT"


@dataclass(frozen=True)
class CapitalCycleSignal:
    """One classified capital-cycle feature snapshot."""

    snapshot: CapitalCycleFeatureSnapshot
    regime: CapitalCycleRegime

    investment_pressure: PressureState
    cashflow_pressure: PressureState

    investment_momentum: InvestmentMomentumState
    cashflow_momentum: CashflowMomentumState

    previous_regime: CapitalCycleRegime | None
    classification_reason: str

    @property
    def investment_pressure_active(self) -> bool:
        """Return whether investment pressure is active."""

        return (
            self.investment_pressure
            is PressureState.ACTIVE
        )

    @property
    def cashflow_pressure_active(self) -> bool:
        """Return whether cashflow pressure is active."""

        return (
            self.cashflow_pressure
            is PressureState.ACTIVE
        )

    @property
    def investment_accelerating(self) -> bool:
        """Return whether investment pressure is accelerating."""

        return (
            self.investment_momentum
            is InvestmentMomentumState.ACCELERATING
        )

    @property
    def investment_easing(self) -> bool:
        """Return whether investment pressure is easing."""

        return (
            self.investment_momentum
            is InvestmentMomentumState.EASING
        )

    @property
    def cashflow_worsening(self) -> bool:
        """Return whether cashflow pressure is worsening."""

        return (
            self.cashflow_momentum
            is CashflowMomentumState.WORSENING
        )

    @property
    def cashflow_improving(self) -> bool:
        """Return whether cashflow pressure is improving."""

        return (
            self.cashflow_momentum
            is CashflowMomentumState.IMPROVING
        )

    def to_payload(self) -> dict[str, object]:
        """Return a dashboard- and API-friendly representation."""

        snapshot = self.snapshot

        return {
            "company_id": snapshot.company_id,
            "fiscal_year": snapshot.fiscal_year,
            "fiscal_quarter": snapshot.fiscal_quarter,
            "period_start": (
                snapshot.period_start.isoformat()
                if snapshot.period_start is not None
                else None
            ),
            "period_end": snapshot.period_end.isoformat(),
            "as_of": snapshot.as_of.isoformat(),
            "regime": self.regime.value,
            "previous_regime": (
                self.previous_regime.value
                if self.previous_regime is not None
                else None
            ),
            "components": {
                "investment_pressure": (
                    self.investment_pressure.value
                ),
                "cashflow_pressure": (
                    self.cashflow_pressure.value
                ),
                "investment_momentum": (
                    self.investment_momentum.value
                ),
                "cashflow_momentum": (
                    self.cashflow_momentum.value
                ),
            },
            "features_pp": {
                "capex_growth_gap": float(
                    snapshot.capex_growth_gap
                    * PERCENT
                ),
                "capex_intensity_yoy_delta": float(
                    snapshot.capex_intensity_yoy_delta
                    * PERCENT
                ),
                "fcf_margin_yoy_delta": float(
                    snapshot.fcf_margin_yoy_delta
                    * PERCENT
                ),
                "capex_growth_gap_qoq_delta": float(
                    snapshot.capex_growth_gap_qoq_delta
                    * PERCENT
                ),
                "capex_intensity_yoy_delta_qoq_delta": float(
                    snapshot
                    .capex_intensity_yoy_delta_qoq_delta
                    * PERCENT
                ),
                "fcf_margin_yoy_delta_qoq_delta": float(
                    snapshot
                    .fcf_margin_yoy_delta_qoq_delta
                    * PERCENT
                ),
            },
            "classification_reason": (
                self.classification_reason
            ),
        }


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


def determine_investment_momentum(
    snapshot: CapitalCycleFeatureSnapshot,
) -> InvestmentMomentumState:
    """Classify the direction of investment pressure."""

    gap_momentum = (
        snapshot.capex_growth_gap_qoq_delta
    )

    intensity_momentum = (
        snapshot
        .capex_intensity_yoy_delta_qoq_delta
    )

    if (
        gap_momentum > ZERO
        and intensity_momentum > ZERO
    ):
        return InvestmentMomentumState.ACCELERATING

    if (
        gap_momentum < ZERO
        and intensity_momentum < ZERO
    ):
        return InvestmentMomentumState.EASING

    if (
        gap_momentum == ZERO
        and intensity_momentum == ZERO
    ):
        return InvestmentMomentumState.FLAT

    return InvestmentMomentumState.MIXED


def determine_cashflow_momentum(
    snapshot: CapitalCycleFeatureSnapshot,
) -> CashflowMomentumState:
    """Classify the direction of cashflow pressure."""

    momentum = (
        snapshot.fcf_margin_yoy_delta_qoq_delta
    )

    if momentum > ZERO:
        return CashflowMomentumState.IMPROVING

    if momentum < ZERO:
        return CashflowMomentumState.WORSENING

    return CashflowMomentumState.FLAT


def build_classification_reason(
    regime: CapitalCycleRegime,
    investment_pressure: PressureState,
    cashflow_pressure: PressureState,
    investment_momentum: InvestmentMomentumState,
    cashflow_momentum: CashflowMomentumState,
    previous_regime: CapitalCycleRegime | None,
) -> str:
    """Build a concise explanation of the regime classification."""

    if regime is CapitalCycleRegime.HARVEST:
        return (
            "Investment pressure has normalized while the "
            "free-cashflow margin is at or above its "
            "prior-year level."
        )

    if regime is CapitalCycleRegime.REACCELERATION:
        previous_label = (
            previous_regime.value
            if previous_regime is not None
            else "an easing state"
        )

        return (
            "Investment pressure is accelerating again after "
            f"{previous_label}, while cashflow pressure is "
            "active or worsening."
        )

    if regime is CapitalCycleRegime.TRANSITION:
        improvements: list[str] = []

        if (
            investment_momentum
            is InvestmentMomentumState.EASING
        ):
            improvements.append(
                "investment momentum is easing"
            )

        if (
            cashflow_momentum
            is CashflowMomentumState.IMPROVING
        ):
            improvements.append(
                "cashflow momentum is improving"
            )

        improvement_text = " and ".join(
            improvements
        )

        return (
            "Investment pressure remains active, but "
            f"{improvement_text}."
        )

    if regime is CapitalCycleRegime.EXPANSION:
        return (
            "Investment and cashflow pressure are active "
            "without sufficient evidence of easing."
        )

    return (
        "The component states do not support a clear "
        "expansion, transition, harvest, or "
        "reacceleration regime."
    )


def classify_capital_cycle_snapshot(
    snapshot: CapitalCycleFeatureSnapshot,
    previous_signal: CapitalCycleSignal | None,
) -> CapitalCycleSignal:
    """Classify one capital-cycle feature snapshot."""

    investment_pressure = (
        PressureState.ACTIVE
        if (
            snapshot.capex_growth_gap > ZERO
            and snapshot.capex_intensity_yoy_delta
            > ZERO
        )
        else PressureState.INACTIVE
    )

    cashflow_pressure = (
        PressureState.ACTIVE
        if snapshot.fcf_margin_yoy_delta < ZERO
        else PressureState.INACTIVE
    )

    investment_momentum = (
        determine_investment_momentum(
            snapshot
        )
    )

    cashflow_momentum = (
        determine_cashflow_momentum(
            snapshot
        )
    )

    investment_pressure_active = (
        investment_pressure
        is PressureState.ACTIVE
    )

    cashflow_pressure_active = (
        cashflow_pressure
        is PressureState.ACTIVE
    )

    investment_accelerating = (
        investment_momentum
        is InvestmentMomentumState.ACCELERATING
    )

    investment_easing = (
        investment_momentum
        is InvestmentMomentumState.EASING
    )

    cashflow_worsening = (
        cashflow_momentum
        is CashflowMomentumState.WORSENING
    )

    cashflow_improving = (
        cashflow_momentum
        is CashflowMomentumState.IMPROVING
    )

    harvest_conditions = (
        snapshot.capex_growth_gap <= ZERO
        and snapshot.capex_intensity_yoy_delta
        <= ZERO
        and snapshot.fcf_margin_yoy_delta
        >= ZERO
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

    previous_regime = (
        previous_signal.regime
        if previous_signal is not None
        else None
    )

    classification_reason = (
        build_classification_reason(
            regime=regime,
            investment_pressure=investment_pressure,
            cashflow_pressure=cashflow_pressure,
            investment_momentum=investment_momentum,
            cashflow_momentum=cashflow_momentum,
            previous_regime=previous_regime,
        )
    )

    return CapitalCycleSignal(
        snapshot=snapshot,
        regime=regime,
        investment_pressure=investment_pressure,
        cashflow_pressure=cashflow_pressure,
        investment_momentum=investment_momentum,
        cashflow_momentum=cashflow_momentum,
        previous_regime=previous_regime,
        classification_reason=classification_reason,
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