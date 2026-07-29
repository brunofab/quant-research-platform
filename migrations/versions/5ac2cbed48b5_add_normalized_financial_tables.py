"""Add normalized financial tables

Revision ID: 5ac2cbed48b5
Revises: 05705ee59bdd
Create Date: 2026-07-29 21:36:11.192949

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5ac2cbed48b5'
down_revision: str | Sequence[str] | None = '05705ee59bdd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "normalized_financials",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "source_key",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "metric",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "value",
            sa.Numeric(precision=30, scale=6),
            nullable=False,
        ),
        sa.Column(
            "unit",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "period_type",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "fiscal_year",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "fiscal_quarter",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "period_start",
            sa.Date(),
            nullable=True,
        ),
        sa.Column(
            "period_end",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "available_at",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "derivation_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_normalized_financials_source_key",
        "normalized_financials",
        ["source_key"],
        unique=True,
    )

    op.create_index(
        "ix_normalized_financials_company_id",
        "normalized_financials",
        ["company_id"],
    )

    op.create_index(
        "ix_normalized_financials_metric",
        "normalized_financials",
        ["metric"],
    )

    op.create_index(
        "ix_normalized_financials_period_type",
        "normalized_financials",
        ["period_type"],
    )

    op.create_index(
        "ix_normalized_financials_fiscal_year",
        "normalized_financials",
        ["fiscal_year"],
    )

    op.create_index(
        "ix_normalized_financials_period_end",
        "normalized_financials",
        ["period_end"],
    )

    op.create_index(
        "ix_normalized_financials_available_at",
        "normalized_financials",
        ["available_at"],
    )

    op.create_table(
        "normalized_financial_sources",
        sa.Column(
            "normalized_financial_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "financial_fact_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "coefficient",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["normalized_financial_id"],
            ["normalized_financials.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["financial_fact_id"],
            ["financial_facts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "normalized_financial_id",
            "financial_fact_id",
        ),
    )

    op.create_index(
        "ix_normalized_financial_sources_financial_fact_id",
        "normalized_financial_sources",
        ["financial_fact_id"],
    )

def downgrade() -> None:
    op.drop_table("normalized_financial_sources")
    op.drop_table("normalized_financials")