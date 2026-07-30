import argparse
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.connection import (
    create_database_engine,
)
from quant_research.database.models import Company
from quant_research.normalization.capex import normalize_capex
from quant_research.normalization.cfo import normalize_cfo
from quant_research.normalization.fcf import normalize_fcf
from quant_research.normalization.fiscal_calendar import (
    backfill_historical_fiscal_periods,
    sync_fiscal_periods,
)
from quant_research.normalization.ratios import (
    normalize_capex_intensity,
    normalize_fcf_margin,
)
from quant_research.normalization.revenue import (
    normalize_revenue,
)

Normalizer = Callable[
    [Session, Company],
    tuple[int, int],
]


NORMALIZERS: dict[str, Normalizer] = {
    "revenue": normalize_revenue,
    "cfo": normalize_cfo,
    "capex": normalize_capex,
    "fcf": normalize_fcf,
    "capex_intensity": normalize_capex_intensity,
    "fcf_margin": normalize_fcf_margin,
}


METRIC_DEPENDENCIES: dict[
    str,
    tuple[str, ...],
] = {
    "revenue": (),
    "cfo": (),
    "capex": (),
    "fcf": (
        "cfo",
        "capex",
    ),
    "capex_intensity": (
        "capex",
        "revenue",
    ),
    "fcf_margin": (
        "fcf",
        "revenue",
    ),
}


NORMALIZATION_ORDER = (
    "revenue",
    "cfo",
    "capex",
    "fcf",
    "capex_intensity",
    "fcf_margin",
)


def resolve_metric_order(
    requested_metrics: list[str],
) -> list[str]:
    """Add dependencies and return a safe execution order."""

    resolved: set[str] = set()
    visiting: set[str] = set()

    def add_metric(metric: str) -> None:
        if metric in resolved:
            return

        if metric in visiting:
            raise ValueError(
                "Circular normalization dependency involving "
                f"{metric}."
            )

        visiting.add(metric)

        for dependency in METRIC_DEPENDENCIES[metric]:
            add_metric(dependency)

        visiting.remove(metric)
        resolved.add(metric)

    for metric in requested_metrics:
        add_metric(metric)

    return [
        metric
        for metric in NORMALIZATION_ORDER
        if metric in resolved
    ]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Build the fiscal calendar and normalize "
            "financial metrics for one company."
        )
    )

    parser.add_argument(
        "--ticker",
        required=True,
        help="Company ticker, for example GOOGL or MSFT.",
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--all",
        action="store_true",
        help="Normalize all supported metrics.",
    )

    mode.add_argument(
        "--metrics",
        nargs="+",
        choices=NORMALIZATION_ORDER,
        help=(
            "Normalize selected metrics. Required dependencies "
            "are added automatically."
        ),
    )

    mode.add_argument(
        "--calendar-only",
        action="store_true",
        help="Only synchronize the fiscal calendar.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ticker = args.ticker.upper()

    if args.calendar_only:
        requested_metrics: list[str] = []
    elif args.all:
        requested_metrics = list(
            NORMALIZATION_ORDER
        )
    else:
        requested_metrics = list(
            args.metrics
        )

    metric_order = resolve_metric_order(
        requested_metrics
    )

    stages = [
        "fiscal_calendar",
        *metric_order,
    ]

    print(
        f"{ticker} normalization plan: "
        + " -> ".join(stages)
    )

    engine = create_database_engine()

    metric_results: dict[
        str,
        tuple[int, int],
    ] = {}

    with Session(engine) as session:
        company = session.scalar(
            select(Company).where(
                Company.ticker == ticker
            )
        )

        if company is None:
            raise ValueError(
                f"{ticker} does not exist in companies. "
                "Ingest its SEC filings first."
            )

        try:
            (
                authoritative_inserted,
                authoritative_existing,
            ) = sync_fiscal_periods(
                session,
                company,
            )

            historical_backfilled = (
                backfill_historical_fiscal_periods(
                    session,
                    company,
                )
            )

            for metric in metric_order:
                normalizer = NORMALIZERS[metric]

                inserted, skipped = normalizer(
                    session,
                    company,
                )

                metric_results[metric] = (
                    inserted,
                    skipped,
                )

            session.commit()

        except Exception:
            session.rollback()
            raise

    print(
        f"{ticker} fiscal calendar: "
        f"{authoritative_inserted} authoritative inserted, "
        f"{historical_backfilled} historical backfilled, "
        f"{authoritative_existing} already existed."
    )

    for metric in metric_order:
        inserted, skipped = metric_results[metric]

        print(
            f"{ticker} {metric} normalization: "
            f"{inserted} inserted, "
            f"{skipped} already existed."
        )


if __name__ == "__main__":
    main()