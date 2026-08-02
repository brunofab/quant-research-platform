from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.models import Company
from quant_research.normalization.fiscal_period_resolver import (
    FiscalPeriodResolver,
)
from quant_research.signals.capital_cycle_confirmation import (
    ConfirmedCapitalCycleSignal,
    confirm_capital_cycle_signals,
)
from quant_research.signals.capital_cycle_features import (
    SnapshotVintage,
    build_capital_cycle_feature_snapshots,
    load_capital_cycle_feature_observations,
    select_snapshot_per_period,
)
from quant_research.signals.capital_cycle_regime import (
    CapitalCycleSignal,
    classify_capital_cycle_snapshots,
)
from quant_research.signals.capital_cycle_thresholds import (
    CapitalCycleThresholds,
)


@dataclass(frozen=True)
class CompanySignalSeries:
    """Raw and confirmed signal histories for one company."""

    ticker: str
    raw_signals: list[CapitalCycleSignal]
    confirmed_signals: list[ConfirmedCapitalCycleSignal]


def deduplicate_tickers(
    tickers: list[str],
) -> list[str]:
    """Normalize tickers while preserving their requested order."""

    normalized: list[str] = []
    seen: set[str] = set()

    for ticker in tickers:
        canonical = ticker.upper()

        if canonical in seen:
            continue

        seen.add(canonical)
        normalized.append(canonical)

    return normalized


def resolve_universe_tickers(
    session: Session,
    requested_tickers: list[str] | None,
) -> list[str]:
    """Resolve requested tickers or return every stored company."""

    if requested_tickers is not None:
        tickers = deduplicate_tickers(
            requested_tickers
        )

        if not tickers:
            raise ValueError(
                "At least one ticker must be supplied."
            )

        return tickers

    tickers = list(
        session.scalars(
            select(Company.ticker).order_by(
                Company.ticker
            )
        )
    )

    if not tickers:
        raise ValueError(
            "No companies exist in the database."
        )

    return tickers


def load_companies(
    session: Session,
    tickers: list[str],
) -> list[Company]:
    """Load companies in the same order as the requested tickers."""

    companies_by_ticker = {
        company.ticker: company
        for company in session.scalars(
            select(Company).where(
                Company.ticker.in_(tickers)
            )
        ).all()
    }

    missing = [
        ticker
        for ticker in tickers
        if ticker not in companies_by_ticker
    ]

    if missing:
        raise ValueError(
            "Unknown company ticker(s): "
            + ", ".join(missing)
            + "."
        )

    return [
        companies_by_ticker[ticker]
        for ticker in tickers
    ]


def build_company_signal_series(
    session: Session,
    company: Company,
    vintage: SnapshotVintage,
    as_of: date | None,
    thresholds: CapitalCycleThresholds,
    confirmation_hits: int,
    confirmation_window: int,
) -> CompanySignalSeries:
    """Build raw and confirmed signals for one company."""

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

    selected_per_period = (
        select_snapshot_per_period(
            snapshots=snapshots,
            vintage=vintage,
            as_of=as_of,
            limit=None,
        )
    )

    raw_signals = classify_capital_cycle_snapshots(
        snapshots=selected_per_period,
        thresholds=thresholds,
    )

    confirmed_signals = confirm_capital_cycle_signals(
        raw_signals=raw_signals,
        confirmation_required=confirmation_hits,
        confirmation_window=confirmation_window,
    )

    return CompanySignalSeries(
        ticker=company.ticker,
        raw_signals=raw_signals,
        confirmed_signals=confirmed_signals,
    )


def build_universe_series(
    session: Session,
    tickers: list[str],
    vintage: SnapshotVintage,
    as_of: date | None,
    thresholds: CapitalCycleThresholds,
    confirmation_hits: int,
    confirmation_window: int,
) -> list[CompanySignalSeries]:
    """Build signal histories for one company universe."""

    companies = load_companies(
        session=session,
        tickers=tickers,
    )

    return [
        build_company_signal_series(
            session=session,
            company=company,
            vintage=vintage,
            as_of=as_of,
            thresholds=thresholds,
            confirmation_hits=confirmation_hits,
            confirmation_window=confirmation_window,
        )
        for company in companies
    ]


def percentage_points_number(
    value: Decimal,
) -> float:
    """Convert a ratio into a JSON-compatible percentage-point number."""

    return float(
        value * Decimal(100)
    )


def build_universe_company_payload(
    company_series: CompanySignalSeries,
) -> dict[str, object]:
    """Build one structured universe-overview company row."""

    if not company_series.confirmed_signals:
        return {
            "ticker": company_series.ticker,
            "status": "no_data",
        }

    signal = company_series.confirmed_signals[-1]
    snapshot = signal.snapshot

    return {
        "ticker": company_series.ticker,
        "status": "ok",
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
            "capex_growth_gap": percentage_points_number(
                snapshot.capex_growth_gap
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
                    snapshot.capex_intensity_yoy_delta_qoq_delta
                )
            ),
            "fcf_margin_yoy_delta_qoq_delta": (
                percentage_points_number(
                    snapshot.fcf_margin_yoy_delta_qoq_delta
                )
            ),
        },
    }


def build_universe_classifier_payload(
    series: list[CompanySignalSeries],
    thresholds: CapitalCycleThresholds,
) -> dict[str, object]:
    """Build structured overview output for one classifier profile."""

    return {
        "classifier": thresholds.name,
        "companies": [
            build_universe_company_payload(
                company_series
            )
            for company_series in series
        ],
    }


def build_universe_overview(
    session: Session,
    requested_tickers: list[str] | None,
    vintage: SnapshotVintage,
    as_of: date | None,
    threshold_profiles: list[CapitalCycleThresholds],
    confirmation_hits: int,
    confirmation_window: int,
) -> dict[str, object]:
    """Build the complete reusable universe-overview payload."""

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

    tickers = resolve_universe_tickers(
        session=session,
        requested_tickers=requested_tickers,
    )

    classifier_payloads: list[
        dict[str, object]
    ] = []

    for thresholds in threshold_profiles:
        series = build_universe_series(
            session=session,
            tickers=tickers,
            vintage=vintage,
            as_of=as_of,
            thresholds=thresholds,
            confirmation_hits=confirmation_hits,
            confirmation_window=confirmation_window,
        )

        classifier_payloads.append(
            build_universe_classifier_payload(
                series=series,
                thresholds=thresholds,
            )
        )

    return {
        "schema_version": 1,
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

