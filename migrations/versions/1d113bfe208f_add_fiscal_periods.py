"""Add fiscal periods

Revision ID: 1d113bfe208f
Revises: 5ac2cbed48b5
Create Date: 2026-07-29 22:15:56.141054

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d113bfe208f'
down_revision: Union[str, Sequence[str], None] = '5ac2cbed48b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fiscal_periods",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.BigInteger(),
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
            nullable=False,
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
            "source_filing_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fiscal_quarter BETWEEN 1 AND 4",
            name="ck_fiscal_periods_quarter",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_filing_id"],
            ["filings.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_quarter",
            name="uq_fiscal_periods_company_year_quarter",
        ),
    )

    op.create_index(
        "ix_fiscal_periods_company_id",
        "fiscal_periods",
        ["company_id"],
    )

    op.create_index(
        "ix_fiscal_periods_fiscal_year",
        "fiscal_periods",
        ["fiscal_year"],
    )

    op.create_index(
        "ix_fiscal_periods_company_period_end",
        "fiscal_periods",
        ["company_id", "period_end"],
    )


def downgrade() -> None:
    op.drop_table("fiscal_periods")
