from datetime import date

from sqlalchemy.orm import Session

from quant_research.signals.capital_cycle_confirmation import (
    ConfirmedCapitalCycleSignal,
)
from quant_research.signals.capital_cycle_features import (
    SnapshotVintage,
)
from quant_research.signals.capital_cycle_thresholds import (
    CapitalCycleThresholds,
)
from quant_research.signals.universe import (
    build_company_signal_series,
    load_companies,
    percentage_points_number,
)


def build_history_period_payload(
    signal: ConfirmedCapitalCycleSignal,
) -> dict[str, object]:
    """Build one dashboard-ready historical period."""

    snapshot = signal.snapshot

    return {
        "fiscal_period": (
            f"FY{snapshot.fiscal_year} "
            f"Q{snapshot.fiscal_quarter}"
        ),
        "fiscal_year": snapshot.fiscal_year,
        "fiscal_quarter": snapshot.fiscal_quarter,
        "as_of": snapshot.as_of.isoformat(),
        "confirmed_regime": signal.regime.value,
        "raw_regime": signal.raw_regime.value,
        "candidate_regime": (
            signal.candidate_regime.value
            if signal.candidate_regime is not None
            else None
        ),
        "candidate_hits": signal.candidate_hits,
        "confirmation_required": (
            signal.confirmation_required
        ),
        "confirmation_pending": (
            signal.confirmation_pending
        ),
        "confirmation_progress": (
            f"{signal.candidate_hits}/"
            f"{signal.confirmation_required}"
            if signal.confirmation_pending
            else None
        ),
        "changed_this_period": (
            signal.changed_this_period
        ),
        "features_percentage_points": {
            "capex_growth_gap": (
                percentage_points_number(
                    snapshot.capex_growth_gap
                )
            ),
            "capex_intensity_yoy_delta": (
                percentage_points_number(
                    snapshot.capex_intensity_yoy_delta
                )
            ),
            "fcf_margin_yoy_delta": (
                percentage_points_number(
                    snapshot.fcf_margin_yoy_delta
                )
            ),
            "capex_growth_gap_qoq_delta": (
                percentage_points_number(
                    snapshot.capex_growth_gap_qoq_delta
                )
            ),
            "capex_intensity_yoy_delta_qoq_delta": (
                percentage_points_number(
                    snapshot
                    .capex_intensity_yoy_delta_qoq_delta
                )
            ),
            "fcf_margin_yoy_delta_qoq_delta": (
                percentage_points_number(
                    snapshot
                    .fcf_margin_yoy_delta_qoq_delta
                )
            ),
        },
    }


def build_company_history(
    session: Session,
    ticker: str,
    vintage: SnapshotVintage,
    as_of: date | None,
    threshold_profiles: list[CapitalCycleThresholds],
    confirmation_hits: int,
    confirmation_window: int,
    limit: int | None = None,
) -> dict[str, object]:
    """Build historical capital-cycle data for one company."""

    if confirmation_hits <= 0:
        raise ValueError(
            "confirmation_hits must be greater than zero."
        )

    if confirmation_window <= 0:
        raise ValueError(
            "confirmation_window must be greater than zero."
        )

    if confirmation_hits > confirmation_window:
        raise ValueError(
            "confirmation_hits cannot exceed "
            "confirmation_window."
        )

    if limit is not None and limit <= 0:
        raise ValueError(
            "limit must be greater than zero."
        )

    canonical_ticker = ticker.strip().upper()

    if not canonical_ticker:
        raise ValueError(
            "Ticker cannot be empty."
        )

    company = load_companies(
        session=session,
        tickers=[canonical_ticker],
    )[0]

    classifier_payloads: list[
        dict[str, object]
    ] = []

    for thresholds in threshold_profiles:
        series = build_company_signal_series(
            session=session,
            company=company,
            vintage=vintage,
            as_of=as_of,
            thresholds=thresholds,
            confirmation_hits=confirmation_hits,
            confirmation_window=confirmation_window,
        )

        signals = series.confirmed_signals

        if limit is not None:
            signals = signals[-limit:]

        classifier_payloads.append(
            {
                "classifier": thresholds.name,
                "periods": [
                    build_history_period_payload(signal)
                    for signal in signals
                ],
            }
        )

    return {
        "schema_version": 1,
        "ticker": company.ticker,
        "requested_as_of": (
            as_of.isoformat()
            if as_of is not None
            else None
        ),
        "snapshot_vintage": vintage.value,
        "units": {
            "features": "percentage_points",
        },
        "confirmation": {
            "required_hits": confirmation_hits,
            "window_quarters": confirmation_window,
        },
        "classifiers": classifier_payloads,
    }
