from collections import Counter, deque
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
    candidate_hits: int

    confirmation_required: int
    confirmation_window: int

    changed_this_period: bool
    sequence_restarted: bool

    window_regimes: tuple[CapitalCycleRegime, ...]

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
            "candidate_hits": self.candidate_hits,
            "confirmation_required": (
                self.confirmation_required
            ),
            "confirmation_window": (
                self.confirmation_window
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
            "window_regimes": [
                regime.value
                for regime in self.window_regimes
            ],
        }


def signal_period_key(
    signal: CapitalCycleSignal,
) -> tuple[int, int]:
    """Return the fiscal-period key of one raw signal."""

    return (
        signal.snapshot.fiscal_year,
        signal.snapshot.fiscal_quarter,
    )


def summarize_candidate(
    window_regimes: tuple[CapitalCycleRegime, ...],
    confirmed_regime: CapitalCycleRegime,
) -> tuple[
    CapitalCycleRegime | None,
    int,
]:
    """Return the strongest unconfirmed regime in the window."""

    eligible_regimes = [
        regime
        for regime in window_regimes
        if regime
        not in {
            confirmed_regime,
            CapitalCycleRegime.MIXED,
        }
    ]

    if not eligible_regimes:
        return None, 0

    counts: Counter[
        CapitalCycleRegime
    ] = Counter(eligible_regimes)

    highest_count = max(
        counts.values()
    )

    tied_regimes = {
        regime
        for regime, count in counts.items()
        if count == highest_count
    }

    # If multiple candidates have the same number of hits,
    # use the most recently observed one for display.
    candidate = next(
        regime
        for regime in reversed(window_regimes)
        if regime in tied_regimes
    )

    return candidate, highest_count


def find_confirmed_candidate(
    window_regimes: tuple[CapitalCycleRegime, ...],
    confirmed_regime: CapitalCycleRegime,
    confirmation_required: int,
) -> CapitalCycleRegime | None:
    """Return a uniquely confirmed candidate from the window."""

    eligible_regimes = [
        regime
        for regime in window_regimes
        if regime
        not in {
            confirmed_regime,
            CapitalCycleRegime.MIXED,
        }
    ]

    counts: Counter[
        CapitalCycleRegime
    ] = Counter(eligible_regimes)

    qualifying_regimes = [
        regime
        for regime, count in counts.items()
        if count >= confirmation_required
    ]

    # With the normal 2-of-3 rule there can only be one.
    # For other configurations, refuse to choose if tied.
    if len(qualifying_regimes) != 1:
        return None

    return qualifying_regimes[0]


def confirm_capital_cycle_signals(
    raw_signals: list[CapitalCycleSignal],
    confirmation_required: int = 2,
    confirmation_window: int = 3,
) -> list[ConfirmedCapitalCycleSignal]:
    """Stabilize raw regimes using rolling-window confirmation."""

    if confirmation_required <= 0:
        raise ValueError(
            "confirmation_required must be greater than zero."
        )

    if confirmation_window <= 0:
        raise ValueError(
            "confirmation_window must be greater than zero."
        )

    if confirmation_required > confirmation_window:
        raise ValueError(
            "confirmation_required cannot exceed "
            "confirmation_window."
        )

    ordered = sorted(
        raw_signals,
        key=signal_period_key,
    )

    confirmed_signals: list[
        ConfirmedCapitalCycleSignal
    ] = []

    confirmed_regime: CapitalCycleRegime | None = None

    regime_window: deque[
        CapitalCycleRegime
    ] = deque(
        maxlen=confirmation_window
    )

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
            # A missing quarter starts a new independent sequence.
            regime_window.clear()
            regime_window.append(
                raw_signal.regime
            )

            confirmed_regime = (
                raw_signal.regime
            )

            candidate_regime = None
            candidate_hits = 0

        else:
            regime_window.append(
                raw_signal.regime
            )

            if confirmed_regime is None:
                raise ValueError(
                    "Confirmed regime was not initialized."
                )

            window_snapshot = tuple(
                regime_window
            )

            confirmed_candidate = (
                find_confirmed_candidate(
                    window_regimes=window_snapshot,
                    confirmed_regime=confirmed_regime,
                    confirmation_required=(
                        confirmation_required
                    ),
                )
            )

            if confirmed_candidate is not None:
                confirmed_regime = (
                    confirmed_candidate
                )

                changed_this_period = True

                # Evidence used to confirm this regime must not
                # immediately be reused to confirm a reversal.
                regime_window.clear()
                regime_window.append(
                    raw_signal.regime
                )

                candidate_regime = None
                candidate_hits = 0

            else:
                (
                    candidate_regime,
                    candidate_hits,
                ) = summarize_candidate(
                    window_regimes=window_snapshot,
                    confirmed_regime=confirmed_regime,
                )

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
                candidate_hits=candidate_hits,
                confirmation_required=(
                    confirmation_required
                ),
                confirmation_window=(
                    confirmation_window
                ),
                changed_this_period=(
                    changed_this_period
                ),
                sequence_restarted=(
                    sequence_restarted
                ),
                window_regimes=tuple(
                    regime_window
                ),
            )
        )

        previous_period = current_period

    return confirmed_signals