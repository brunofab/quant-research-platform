from dataclasses import dataclass

from quant_research.signals.capital_cycle_features import (
    CapitalCycleFeatureSnapshot,
)
from quant_research.signals.capital_cycle_regime import (
    CapitalCycleRegime,
    CapitalCycleSignal,
    previous_fiscal_period_key,
)


@dataclass(frozen=True)
class ConfirmedCapitalCycleSignal:
    """A raw signal together with its stabilized dashboard regime."""

    snapshot: CapitalCycleFeatureSnapshot
    regime: CapitalCycleRegime
    raw_signal: CapitalCycleSignal

    candidate_regime: CapitalCycleRegime | None
    candidate_age_quarters: int
    confirmation_required: int

    changed_this_period: bool
    sequence_restarted: bool

    @property
    def raw_regime(self) -> CapitalCycleRegime:
        """Return the unstabilized regime classification."""

        return self.raw_signal.regime

    @property
    def confirmation_pending(self) -> bool:
        """Return whether a potential regime change is pending."""

        return self.candidate_regime is not None

    def to_payload(self) -> dict[str, object]:
        """Return a dashboard- and API-friendly representation."""

        return {
            "raw_signal": self.raw_signal.to_payload(),
            "confirmed_regime": self.regime.value,
            "candidate_regime": (
                self.candidate_regime.value
                if self.candidate_regime is not None
                else None
            ),
            "candidate_age_quarters": (
                self.candidate_age_quarters
            ),
            "confirmation_required": (
                self.confirmation_required
            ),
            "confirmation_pending": (
                self.confirmation_pending
            ),
            "changed_this_period": (
                self.changed_this_period
            ),
            "sequence_restarted": (
                self.sequence_restarted
            ),
        }


def signal_period_key(
    signal: CapitalCycleSignal,
) -> tuple[int, int]:
    """Return the fiscal-period key of one raw signal."""

    return (
        signal.snapshot.fiscal_year,
        signal.snapshot.fiscal_quarter,
    )


def confirm_capital_cycle_signals(
    raw_signals: list[CapitalCycleSignal],
    confirmation_required: int = 2,
) -> list[ConfirmedCapitalCycleSignal]:
    """Stabilize raw regimes using consecutive-quarter confirmation."""

    if confirmation_required <= 0:
        raise ValueError(
            "confirmation_required must be greater than zero."
        )

    ordered = sorted(
        raw_signals,
        key=signal_period_key,
    )

    confirmed_signals: list[
        ConfirmedCapitalCycleSignal
    ] = []

    confirmed_regime: CapitalCycleRegime | None = None
    candidate_regime: CapitalCycleRegime | None = None
    candidate_age = 0

    previous_period: tuple[int, int] | None = None

    for raw_signal in ordered:
        current_period = signal_period_key(
            raw_signal
        )

        expected_previous_period = (
            previous_fiscal_period_key(
                raw_signal.snapshot.fiscal_year,
                raw_signal.snapshot.fiscal_quarter,
            )
        )

        sequence_restarted = (
            previous_period is None
            or previous_period
            != expected_previous_period
        )

        changed_this_period = False

        if sequence_restarted:
            # A missing fiscal period breaks the confirmation chain.
            # Start a new sequence from the current raw regime.
            confirmed_regime = raw_signal.regime
            candidate_regime = None
            candidate_age = 0

        elif raw_signal.regime is confirmed_regime:
            # The raw signal agrees with the confirmed regime.
            candidate_regime = None
            candidate_age = 0

        elif raw_signal.regime is CapitalCycleRegime.MIXED:
            # MIXED represents uncertainty. It does not replace
            # an already confirmed economic regime.
            candidate_regime = None
            candidate_age = 0

        else:
            if candidate_regime is raw_signal.regime:
                candidate_age += 1
            else:
                candidate_regime = raw_signal.regime
                candidate_age = 1

            if candidate_age >= confirmation_required:
                confirmed_regime = raw_signal.regime
                candidate_regime = None
                candidate_age = 0
                changed_this_period = True

        if confirmed_regime is None:
            raise ValueError(
                "Confirmed regime was not initialized."
            )

        confirmed_signals.append(
            ConfirmedCapitalCycleSignal(
                snapshot=raw_signal.snapshot,
                regime=confirmed_regime,
                raw_signal=raw_signal,
                candidate_regime=candidate_regime,
                candidate_age_quarters=candidate_age,
                confirmation_required=(
                    confirmation_required
                ),
                changed_this_period=changed_this_period,
                sequence_restarted=sequence_restarted,
            )
        )

        previous_period = current_period

    return confirmed_signals
