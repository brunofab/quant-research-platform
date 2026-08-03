from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
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

    source_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
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

class NormalizedFinancial(Base):
    __tablename__ = "normalized_financials"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    source_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    metric: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    value: Mapped[Decimal] = mapped_column(
        Numeric(30, 6),
        nullable=False,
    )

    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    fiscal_year: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    fiscal_quarter: Mapped[int | None] = mapped_column(
        nullable=True,
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

    available_at: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    derivation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

class NormalizedFinancialSource(Base):
    __tablename__ = "normalized_financial_sources"

    normalized_financial_id: Mapped[int] = mapped_column(
        ForeignKey(
            "normalized_financials.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    financial_fact_id: Mapped[int] = mapped_column(
        ForeignKey(
            "financial_facts.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
        index=True,
    )

    coefficient: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

class NormalizedFinancialDependency(Base):
    __tablename__ = "normalized_financial_dependencies"

    __table_args__ = (
        CheckConstraint(
            "derived_financial_id <> source_financial_id",
            name="ck_normalized_financial_dependencies_not_self",
        ),
    )

    derived_financial_id: Mapped[int] = mapped_column(
        ForeignKey(
            "normalized_financials.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    source_financial_id: Mapped[int] = mapped_column(
        ForeignKey(
            "normalized_financials.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
        index=True,
    )

    coefficient: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

class FiscalPeriod(Base):
    __tablename__ = "fiscal_periods"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_quarter",
            name="uq_fiscal_periods_company_year_quarter",
        ),
        CheckConstraint(
            "fiscal_quarter BETWEEN 1 AND 4",
            name="ck_fiscal_periods_quarter",
        ),
        Index(
            "ix_fiscal_periods_company_period_end",
            "company_id",
            "period_end",
        ),
    )

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

    fiscal_year: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    fiscal_quarter: Mapped[int] = mapped_column(
        nullable=False,
    )

    period_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    source_filing_id: Mapped[int] = mapped_column(
        ForeignKey("filings.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    derivation_type: Mapped[str] = mapped_column(
    String(50),
    nullable=False,
    )

    source_fact_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "financial_facts.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )


class PipelineRun(Base):
    """Record one execution of a data pipeline."""

    __tablename__ = "pipeline_runs"

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'running', "
            "'succeeded', "
            "'partial', "
            "'failed'"
            ")",
            name="ck_pipeline_runs_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    run_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="running",
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    companies_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    companies_succeeded: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    companies_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    records_inserted: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )



class DataQualityRun(Base):
    """Record one execution of a data-quality suite."""

    __tablename__ = "data_quality_runs"

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'running', "
            "'passed', "
            "'warning', "
            "'failed'"
            ")",
            name="ck_data_quality_runs_status",
        ),
        CheckConstraint(
            "checks_executed >= 0 AND "
            "records_checked >= 0 AND "
            "issues_found >= 0 AND "
            "blocking_issues >= 0 AND "
            "blocking_issues <= issues_found",
            name="ck_data_quality_runs_nonnegative_counts",
        ),
        Index(
            "ix_data_quality_runs_dataset_started_at",
            "dataset",
            "started_at",
        ),
        Index(
            "ix_data_quality_runs_pipeline_status",
            "pipeline_run_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    pipeline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "pipeline_runs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    dataset: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    scope_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="global",
    )

    scope_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="running",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    checks_executed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    records_checked: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
    )

    issues_found: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    blocking_issues: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    context_json: Mapped[
        dict[str, object] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )


class DataQualityIssue(Base):
    """Record one issue found by a quality check."""

    __tablename__ = "data_quality_issues"

    __table_args__ = (
        CheckConstraint(
            "severity IN ("
            "'info', "
            "'warning', "
            "'error', "
            "'critical'"
            ")",
            name="ck_data_quality_issues_severity",
        ),
        CheckConstraint(
            "period_start IS NULL OR "
            "period_end IS NULL OR "
            "period_start <= period_end",
            name="ck_data_quality_issues_period_order",
        ),
        Index(
            "ix_data_quality_issues_run_severity",
            "data_quality_run_id",
            "severity",
        ),
        Index(
            "ix_data_quality_issues_entity",
            "entity_type",
            "entity_key",
        ),
        Index(
            "ix_data_quality_issues_dataset_check",
            "dataset",
            "check_name",
        ),
        Index(
            "ix_data_quality_issues_company_period",
            "company_id",
            "period_end",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    data_quality_run_id: Mapped[int] = mapped_column(
        ForeignKey(
            "data_quality_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    company_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "companies.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    entity_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    dataset: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    metric: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    check_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    blocking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    period_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    period_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    available_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    actual_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    expected_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    context_json: Mapped[
        dict[str, object] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )