"""Create initial financial data schema

Revision ID: f631761bcd35
Revises: 
Create Date: 2026-07-29 17:31:41.766113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f631761bcd35'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("exchange", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cik"),
        sa.UniqueConstraint("ticker"),
    )

    op.create_index("ix_companies_ticker", "companies", ["ticker"])
    op.create_index("ix_companies_cik", "companies", ["cik"])

    op.create_table(
        "filings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("accession_number", sa.String(length=30), nullable=False),
        sa.Column("form", sa.String(length=20), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("primary_document", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accession_number"),
    )

    op.create_index("ix_filings_company_id", "filings", ["company_id"])
    op.create_index("ix_filings_form", "filings", ["form"])

    op.create_table(
        "financial_facts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("taxonomy", sa.String(length=50), nullable=False),
        sa.Column("concept", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Numeric(precision=30, scale=6), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("filed_at", sa.Date(), nullable=False),
        sa.Column("accession_number", sa.String(length=30), nullable=True),
        sa.Column("form", sa.String(length=20), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_period", sa.String(length=10), nullable=True),
        sa.Column("frame", sa.String(length=30), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_financial_facts_company_id",
        "financial_facts",
        ["company_id"],
    )
    op.create_index(
        "ix_financial_facts_concept",
        "financial_facts",
        ["concept"],
    )
    op.create_index(
        "ix_financial_facts_period_end",
        "financial_facts",
        ["period_end"],
    )
    op.create_index(
        "ix_financial_facts_filed_at",
        "financial_facts",
        ["filed_at"],
    )
    op.create_index(
        "ix_financial_facts_accession_number",
        "financial_facts",
        ["accession_number"],
    )


def downgrade() -> None:
    op.drop_table("financial_facts")
    op.drop_table("filings")
    op.drop_table("companies")
