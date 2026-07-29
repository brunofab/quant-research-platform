import time
from typing import Any

import httpx

from quant_research.settings import get_settings


SEC_BASE_URL = "https://data.sec.gov"


def format_cik(cik: str | int) -> str:
    """Return a SEC CIK padded to exactly 10 digits."""
    return str(cik).zfill(10)


class SECClient:
    """Small client for the SEC EDGAR JSON APIs."""

    def __init__(self) -> None:
        settings = get_settings()

        self.client = httpx.Client(
            base_url=SEC_BASE_URL,
            headers={
                "User-Agent": settings.sec_user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

        # Deliberately very conservative.
        # 1 second between requests = max ~1 request/sec.
        self.request_delay = 1.0

    def _get_json(self, path: str) -> dict[str, Any]:
        """GET one SEC JSON endpoint with basic retry handling."""

        attempts = 3

        for attempt in range(1, attempts + 1):
            try:
                response = self.client.get(path)

                if response.status_code == 429:
                    # SEC rate-limit response.
                    time.sleep(5 * attempt)
                    continue

                response.raise_for_status()

                time.sleep(self.request_delay)

                return response.json()

            except httpx.HTTPError:
                if attempt == attempts:
                    raise

                time.sleep(2 * attempt)

        raise RuntimeError("SEC request failed unexpectedly.")

    def get_submissions(self, cik: str | int) -> dict[str, Any]:
        cik_padded = format_cik(cik)

        return self._get_json(
            f"/submissions/CIK{cik_padded}.json"
        )

    def get_company_facts(self, cik: str | int) -> dict[str, Any]:
        cik_padded = format_cik(cik)

        return self._get_json(
            f"/api/xbrl/companyfacts/CIK{cik_padded}.json"
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "SECClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
