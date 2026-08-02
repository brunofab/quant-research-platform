import argparse
import sys
from collections.abc import Sequence

from quant_research.pipeline.refresh import (
    PipelineAlreadyRunningError,
    refresh_companies,
)


def parse_tickers(
    value: str,
) -> list[str]:
    """Parse a comma-separated ticker list."""

    tickers = [
        ticker.strip().upper()
        for ticker in value.split(",")
        if ticker.strip()
    ]

    if not tickers:
        raise argparse.ArgumentTypeError(
            "At least one ticker is required."
        )

    return tickers


def build_parser() -> argparse.ArgumentParser:
    """Build the pipeline command-line parser."""

    parser = argparse.ArgumentParser(
        prog="quant_research.pipeline",
        description=(
            "Run tracked quantitative research "
            "data pipelines."
        ),
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    refresh_parser = commands.add_parser(
        "refresh",
        help=(
            "Refresh SEC data, normalized metrics "
            "and signal validation."
        ),
    )

    target_group = (
        refresh_parser.add_mutually_exclusive_group(
            required=True
        )
    )

    target_group.add_argument(
        "--all-companies",
        action="store_true",
        help="Refresh every stored company.",
    )

    target_group.add_argument(
        "--tickers",
        type=parse_tickers,
        help=(
            "Comma-separated ticker subset, for "
            "example GOOGL,MSFT."
        ),
    )

    refresh_parser.add_argument(
        "--skip-signal-validation",
        action="store_true",
        help=(
            "Refresh stored data without validating "
            "capital-cycle signals."
        ),
    )

    return parser


def main(
    arguments: Sequence[str] | None = None,
) -> int:
    """Run the selected pipeline command."""

    parser = build_parser()
    parsed = parser.parse_args(arguments)

    if parsed.command != "refresh":
        parser.error(
            f"Unsupported command: {parsed.command}"
        )

    requested_tickers = (
        None
        if parsed.all_companies
        else parsed.tickers
    )

    try:
        result = refresh_companies(
            requested_tickers=requested_tickers,
            validate_signals=(
                not parsed.skip_signal_validation
            ),
        )
    except PipelineAlreadyRunningError as error:
        print(
            f"Refresh skipped: {error}",
            file=sys.stderr,
        )
        return 75

    return (
        0
        if result.status == "succeeded"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
