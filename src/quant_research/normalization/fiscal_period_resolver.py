from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research.database.models import FiscalPeriod


@dataclass(frozen=True)
class ResolvedFiscalPeriod:
    """Resolved fiscal period for a raw financial fact."""

    fiscal_year: int
    fiscal_quarter: int
    period_start: date | None
    period_end: date


class FiscalPeriodResolver:
    """Resolve economic periods using the company-specific fiscal calendar."""

    def __init__(
        self,
        session: Session,
        company_id: int,
    ) -> None:
        self.company_id = company_id

        periods = list(
            session.scalars(
                select(FiscalPeriod)
                .where(
                    FiscalPeriod.company_id
                    == company_id
                )
                .order_by(FiscalPeriod.period_end)
            ).all()
        )

        if not periods:
            raise ValueError(
                f"No fiscal periods exist for company "
                f"{company_id}."
            )

        self._by_end = {
            period.period_end: period
            for period in periods
        }

    def resolve_by_end(
        self,
        period_end: date,
    ) -> ResolvedFiscalPeriod:
        """Resolve a fiscal quarter from its economic period end."""

        period = self._by_end.get(period_end)

        if period is None:
            raise ValueError(
                "Unable to resolve fiscal period for "
                f"company {self.company_id} with "
                f"period_end={period_end}."
            )

        return ResolvedFiscalPeriod(
            fiscal_year=period.fiscal_year,
            fiscal_quarter=period.fiscal_quarter,
            period_start=period.period_start,
            period_end=period.period_end,
        )

