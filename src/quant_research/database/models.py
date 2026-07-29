from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from quant_research.database.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    ticker: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    cik: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    exchange: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    currency: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    accession_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
    )

    form: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    filing_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    report_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    primary_document: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

class FinancialFact(Base):
    __tablename__ = "financial_facts"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    taxonomy: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    concept: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    value: Mapped[Decimal] = mapped_column(
        Numeric(30, 6),
        nullable=False,
    )

    period_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    filed_at: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    accession_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    form: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    fiscal_year: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    fiscal_period: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    frame: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        default="SEC",
        nullable=False,
    )

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
