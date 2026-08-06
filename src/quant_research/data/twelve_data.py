from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from time import sleep
from typing import Self

import httpx

RETRYABLE_STATUS_CODES = frozenset(
    {
        429,
        500,
        502,
        503,
        504,
    }
)


class TwelveDataError(RuntimeError):
    """Raised when Twelve Data returns unusable data."""


@dataclass(frozen=True, slots=True)
class TwelveDataMetadata:
    """Metadata describing one market instrument."""

    symbol: str
    interval: str
    currency: str
    exchange_timezone: str
    exchange: str | None
    mic_code: str
    asset_type: str


@dataclass(frozen=True, slots=True)
class DailyMarketBar:
    """One parsed daily OHLCV observation."""

    bar_date: date
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int | None


@dataclass(frozen=True, slots=True)
class DailyTimeSeries:
    """A parsed daily time-series response."""

    metadata: TwelveDataMetadata
    bars: tuple[DailyMarketBar, ...]


def require_text(
    mapping: dict[str, object],
    key: str,
) -> str:
    """Read one required non-empty string."""

    value = mapping.get(key)

    if not isinstance(value, str):
        raise TwelveDataError(
            f"Missing or invalid string field: {key}."
        )

    value = value.strip()

    if not value:
        raise TwelveDataError(
            f"Empty string field: {key}."
        )

    return value


def optional_text(
    mapping: dict[str, object],
    key: str,
) -> str | None:
    """Read one optional string."""

    value = mapping.get(key)

    if value is None:
        return None

    if not isinstance(value, str):
        raise TwelveDataError(
            f"Invalid optional string field: {key}."
        )

    value = value.strip()

    return value or None


def parse_decimal(
    mapping: dict[str, object],
    key: str,
) -> Decimal:
    """Parse one positive decimal price."""

    raw_value = require_text(
        mapping,
        key,
    )

    try:
        value = Decimal(raw_value)
    except InvalidOperation as error:
        raise TwelveDataError(
            f"Invalid decimal value for {key}: "
            f"{raw_value!r}."
        ) from error

    if not value.is_finite() or value <= 0:
        raise TwelveDataError(
            f"Non-positive price for {key}: "
            f"{raw_value!r}."
        )

    return value


def parse_volume(
    mapping: dict[str, object],
) -> int | None:
    """Parse an optional non-negative integer volume."""

    raw_value = mapping.get("volume")

    if raw_value in {
        None,
        "",
    }:
        return None

    try:
        decimal_value = Decimal(str(raw_value))
    except InvalidOperation as error:
        raise TwelveDataError(
            f"Invalid volume: {raw_value!r}."
        ) from error

    integral_value = (
        decimal_value.to_integral_value()
    )

    if (
        decimal_value != integral_value
        or integral_value < 0
    ):
        raise TwelveDataError(
            f"Invalid integer volume: {raw_value!r}."
        )

    return int(integral_value)


def parse_daily_bar(
    value: object,
) -> DailyMarketBar:
    """Convert one raw API row into a daily bar."""

    if not isinstance(value, dict):
        raise TwelveDataError(
            "Time-series row is not an object."
        )

    row: dict[str, object] = value

    raw_datetime = require_text(
        row,
        "datetime",
    )

    try:
        bar_date = date.fromisoformat(
            raw_datetime[:10]
        )
    except ValueError as error:
        raise TwelveDataError(
            "Invalid daily-bar date: "
            f"{raw_datetime!r}."
        ) from error

    open_price = parse_decimal(
        row,
        "open",
    )
    high_price = parse_decimal(
        row,
        "high",
    )
    low_price = parse_decimal(
        row,
        "low",
    )
    close_price = parse_decimal(
        row,
        "close",
    )

    if high_price < max(
        open_price,
        low_price,
        close_price,
    ):
        raise TwelveDataError(
            f"Invalid high price for {bar_date}."
        )

    if low_price > min(
        open_price,
        high_price,
        close_price,
    ):
        raise TwelveDataError(
            f"Invalid low price for {bar_date}."
        )

    return DailyMarketBar(
        bar_date=bar_date,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=parse_volume(row),
    )


class TwelveDataClient:
    """Small client for Twelve Data time series."""

    base_url = (
        "https://api.twelvedata.com"
    )

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        api_key = api_key.strip()

        if not api_key:
            raise ValueError(
                "Twelve Data API key is required."
            )

        if max_retries < 0:
            raise ValueError(
                "max_retries cannot be negative."
            )

        self._api_key = api_key
        self._max_retries = max_retries

        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout_seconds,
            headers={
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()

    def request(
        self,
        path: str,
        *,
        params: dict[str, str | int],
    ) -> dict[str, object]:
        """Send one request with bounded retries."""

        for attempt in range(
            self._max_retries + 1
        ):
            try:
                response = self._client.get(
                    path,
                    params=params,
                )
            except httpx.RequestError as error:
                if attempt >= self._max_retries:
                    raise TwelveDataError(
                        "Twelve Data request failed."
                    ) from error
            else:
                if (
                    response.status_code
                    in RETRYABLE_STATUS_CODES
                ):
                    if (
                        attempt
                        >= self._max_retries
                    ):
                        raise TwelveDataError(
                            "Twelve Data returned "
                            "retryable HTTP status "
                            f"{response.status_code}."
                        )
                else:
                    try:
                        response.raise_for_status()
                    except (
                        httpx.HTTPStatusError
                    ) as error:
                        raise TwelveDataError(
                            "Twelve Data returned "
                            f"HTTP status "
                            f"{response.status_code}."
                        ) from error

                    try:
                        payload = response.json()
                    except ValueError as error:
                        raise TwelveDataError(
                            "Twelve Data returned "
                            "invalid JSON."
                        ) from error

                    if not isinstance(
                        payload,
                        dict,
                    ):
                        raise TwelveDataError(
                            "Twelve Data response "
                            "is not a JSON object."
                        )

                    return payload

            sleep(
                min(
                    2**attempt,
                    8,
                )
            )

        raise TwelveDataError(
            "Twelve Data retry loop exited "
            "unexpectedly."
        )

    def fetch_daily_bars(
        self,
        symbol: str,
        *,
        outputsize: int = 5000,
    ) -> DailyTimeSeries:
        """Fetch split-adjusted daily OHLCV bars."""

        symbol = symbol.strip().upper()

        if not symbol:
            raise ValueError(
                "Market symbol is required."
            )

        if not 1 <= outputsize <= 5000:
            raise ValueError(
                "outputsize must be between "
                "1 and 5000."
            )

        payload = self.request(
            "/time_series",
            params={
                "symbol": symbol,
                "interval": "1day",
                "outputsize": outputsize,
                "adjust": "splits",
                "apikey": self._api_key,
            },
        )

        if payload.get("status") == "error":
            code = payload.get("code")
            message = payload.get(
                "message",
            )

            raise TwelveDataError(
                "Twelve Data API error "
                f"{code}: {message}"
            )

        raw_metadata = payload.get("meta")

        if not isinstance(
            raw_metadata,
            dict,
        ):
            raise TwelveDataError(
                "Missing time-series metadata."
            )

        metadata_mapping: dict[
            str,
            object,
        ] = raw_metadata

        metadata = TwelveDataMetadata(
            symbol=require_text(
                metadata_mapping,
                "symbol",
            ),
            interval=require_text(
                metadata_mapping,
                "interval",
            ),
            currency=require_text(
                metadata_mapping,
                "currency",
            ),
            exchange_timezone=require_text(
                metadata_mapping,
                "exchange_timezone",
            ),
            exchange=optional_text(
                metadata_mapping,
                "exchange",
            ),
            mic_code=require_text(
                metadata_mapping,
                "mic_code",
            ),
            asset_type=require_text(
                metadata_mapping,
                "type",
            ),
        )

        raw_values = payload.get("values")

        if not isinstance(
            raw_values,
            list,
        ):
            raise TwelveDataError(
                "Missing time-series values."
            )

        bars = tuple(
            sorted(
                (
                    parse_daily_bar(value)
                    for value in raw_values
                ),
                key=lambda bar: bar.bar_date,
            )
        )

        if not bars:
            raise TwelveDataError(
                f"No daily bars returned for "
                f"{symbol}."
            )

        return DailyTimeSeries(
            metadata=metadata,
            bars=bars,
        )
