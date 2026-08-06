import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import (
    insert as postgresql_insert,
)
from sqlalchemy.orm import Session

from quant_research.data.twelve_data import (
    DailyMarketBar,
    DailyTimeSeries,
    TwelveDataClient,
)
from quant_research.database.connection import (
    create_database_engine,
)
from quant_research.database.models import (
    Company,
    MarketBar,
    MarketInstrument,
)

PROVIDER = "twelve_data"
ADJUSTMENT_TYPE = "split_adjusted"
INTERVAL = "1day"


@dataclass(frozen=True, slots=True)
class MarketIngestionSummary:
    """Summary of one market-data ingestion."""

    ticker: str
    provider_symbol: str
    instrument_created: bool
    bars_received: int
    bars_inserted: int
    bars_seen_again: int


def canonical_decimal(
    value: Decimal,
) -> str:
    """Return a stable decimal representation."""

    text = format(
        value.normalize(),
        "f",
    )

    if "." in text:
        text = text.rstrip("0").rstrip(".")

    return text


def build_market_bar_source_key(
    *,
    provider_symbol: str,
    mic_code: str,
    currency: str,
    bar: DailyMarketBar,
) -> str:
    """Build a deterministic identity for one bar version."""

    identity = [
        PROVIDER,
        provider_symbol,
        mic_code,
        INTERVAL,
        bar.bar_date.isoformat(),
        canonical_decimal(bar.open_price),
        canonical_decimal(bar.high_price),
        canonical_decimal(bar.low_price),
        canonical_decimal(bar.close_price),
        (
            str(bar.volume)
            if bar.volume is not None
            else None
        ),
        currency,
        ADJUSTMENT_TYPE,
    ]

    encoded_identity = json.dumps(
        identity,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(
        encoded_identity
    ).hexdigest()


def load_company(
    session: Session,
    ticker: str,
) -> Company:
    """Load one configured company."""

    ticker = ticker.strip().upper()

    company = session.scalar(
        select(Company).where(
            Company.ticker == ticker
        )
    )

    if company is None:
        raise ValueError(
            f"Unknown company ticker: {ticker}."
        )

    return company


def upsert_market_instrument(
    session: Session,
    *,
    company: Company,
    time_series: DailyTimeSeries,
    observed_at: datetime,
) -> tuple[MarketInstrument, bool]:
    """Create or refresh a provider instrument."""

    metadata = time_series.metadata

    instrument = session.scalar(
        select(MarketInstrument).where(
            MarketInstrument.provider
            == PROVIDER,
            MarketInstrument.provider_symbol
            == metadata.symbol,
            MarketInstrument.mic_code
            == metadata.mic_code,
        )
    )

    if instrument is None:
        instrument = MarketInstrument(
            company_id=company.id,
            provider=PROVIDER,
            provider_symbol=metadata.symbol,
            exchange=metadata.exchange,
            mic_code=metadata.mic_code,
            currency=metadata.currency,
            exchange_timezone=(
                metadata.exchange_timezone
            ),
            asset_type=metadata.asset_type,
            is_active=True,
            updated_at=observed_at,
        )

        session.add(instrument)
        session.flush()

        return instrument, True

    if instrument.company_id != company.id:
        raise ValueError(
            "Provider instrument is already linked "
            "to another company."
        )

    instrument.exchange = metadata.exchange
    instrument.currency = metadata.currency
    instrument.exchange_timezone = (
        metadata.exchange_timezone
    )
    instrument.asset_type = metadata.asset_type
    instrument.is_active = True
    instrument.updated_at = observed_at

    session.flush()

    return instrument, False


def ingest_market_bars(
    session: Session,
    *,
    ticker: str,
    time_series: DailyTimeSeries,
    observed_at: datetime,
) -> MarketIngestionSummary:
    """Persist one fetched daily time series."""

    company = load_company(
        session,
        ticker,
    )

    instrument, instrument_created = (
        upsert_market_instrument(
            session,
            company=company,
            time_series=time_series,
            observed_at=observed_at,
        )
    )

    metadata = time_series.metadata

    rows: list[dict[str, object]] = []

    for bar in time_series.bars:
        source_key = (
            build_market_bar_source_key(
                provider_symbol=(
                    metadata.symbol
                ),
                mic_code=metadata.mic_code,
                currency=metadata.currency,
                bar=bar,
            )
        )

        rows.append(
            {
                "source_key": source_key,
                "instrument_id": instrument.id,
                "interval": INTERVAL,
                "bar_date": bar.bar_date,
                "open_price": bar.open_price,
                "high_price": bar.high_price,
                "low_price": bar.low_price,
                "close_price": bar.close_price,
                "volume": bar.volume,
                "currency": metadata.currency,
                "adjustment_type": (
                    ADJUSTMENT_TYPE
                ),
                "provider": PROVIDER,
                "first_observed_at": (
                    observed_at
                ),
                "last_seen_at": observed_at,
            }
        )

    source_keys = [
        str(row["source_key"])
        for row in rows
    ]

    existing_source_keys = set(
        session.scalars(
            select(MarketBar.source_key).where(
                MarketBar.source_key.in_(
                    source_keys
                )
            )
        )
    )

    inserted_count = (
        len(source_keys)
        - len(existing_source_keys)
    )

    if rows:
        statement = (
            postgresql_insert(MarketBar)
            .values(rows)
            .on_conflict_do_update(
                constraint=(
                    "uq_market_bars_source_key"
                ),
                set_={
                    "last_seen_at": observed_at,
                },
            )
        )

        session.execute(statement)

    return MarketIngestionSummary(
        ticker=company.ticker,
        provider_symbol=metadata.symbol,
        instrument_created=(
            instrument_created
        ),
        bars_received=len(rows),
        bars_inserted=inserted_count,
        bars_seen_again=(
            len(existing_source_keys)
        ),
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Fetch and ingest Twelve Data "
            "daily market bars."
        )
    )

    parser.add_argument(
        "--ticker",
        required=True,
        help=(
            "Internal company ticker, "
            "for example AMZN."
        ),
    )

    parser.add_argument(
        "--symbol",
        help=(
            "Optional provider symbol. "
            "Defaults to the ticker."
        ),
    )

    parser.add_argument(
        "--outputsize",
        type=int,
        default=5000,
        help=(
            "Number of daily bars to request "
            "(1 to 5000)."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Run one market-data ingestion."""

    arguments = parse_arguments()

    ticker = arguments.ticker.strip().upper()
    symbol = (
        arguments.symbol.strip().upper()
        if arguments.symbol
        else ticker
    )

    api_key = os.environ.get(
        "TWELVE_DATA_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "TWELVE_DATA_API_KEY is not set."
        )

    with TwelveDataClient(
        api_key
    ) as client:
        time_series = (
            client.fetch_daily_bars(
                symbol,
                outputsize=(
                    arguments.outputsize
                ),
            )
        )

    observed_at = datetime.now(UTC)
    engine = create_database_engine()

    try:
        with Session(engine) as session:
            try:
                summary = ingest_market_bars(
                    session,
                    ticker=ticker,
                    time_series=time_series,
                    observed_at=observed_at,
                )

                session.commit()
            except Exception:
                session.rollback()
                raise
    finally:
        engine.dispose()

    print(
        f"{summary.ticker}: "
        f"provider symbol "
        f"{summary.provider_symbol}."
    )
    print(
        "Instrument created: "
        f"{'yes' if summary.instrument_created else 'no'}"
    )
    print(
        "Bars received: "
        f"{summary.bars_received}"
    )
    print(
        "Bars inserted: "
        f"{summary.bars_inserted}"
    )
    print(
        "Bars seen again: "
        f"{summary.bars_seen_again}"
    )


if __name__ == "__main__":
    main()
