from __future__ import annotations

import argparse

from quant_research.data_quality.runner import (
    run_data_quality,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Run registered data-quality checks."
        )
    )

    parser.add_argument(
        "--dataset",
        default="normalized_financials",
        choices=[
            "normalized_financials",
        ],
    )

    company_group = (
        parser.add_mutually_exclusive_group(
            required=True
        )
    )

    company_group.add_argument(
        "--all-companies",
        action="store_true",
    )

    company_group.add_argument(
        "--ticker",
        action="append",
        dest="tickers",
        help=(
            "Ticker to check. Repeat the option "
            "to check multiple companies."
        ),
    )

    parser.add_argument(
        "--pipeline-run-id",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--lookback-periods",
        type=int,
        default=12,
    )

    return parser


def main() -> int:
    """Run the selected quality suite."""

    parser = build_parser()
    arguments = parser.parse_args()

    if arguments.lookback_periods < 1:
        parser.error(
            "--lookback-periods must be positive."
        )

    requested_tickers = (
        None
        if arguments.all_companies
        else arguments.tickers
    )

    summary = run_data_quality(
        dataset=arguments.dataset,
        requested_tickers=requested_tickers,
        pipeline_run_id=(
            arguments.pipeline_run_id
        ),
        lookback_periods=(
            arguments.lookback_periods
        ),
    )

    return (
        1
        if summary.status == "failed"
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
