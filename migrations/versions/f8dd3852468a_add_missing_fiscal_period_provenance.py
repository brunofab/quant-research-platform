"""Add missing fiscal period provenance

Revision ID: f8dd3852468a
Revises: 21f5fdcb3b3c
Create Date: 2026-07-29 23:13:07.855871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8dd3852468a'
down_revision: Union[str, Sequence[str], None] = '21f5fdcb3b3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fiscal_periods",
        sa.Column(
            "derivation_type",
            sa.String(length=50),
            nullable=False,
            server_default="filing_report_date",
        ),
    )

    op.add_column(
        "fiscal_periods",
        sa.Column(
            "source_fact_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_fiscal_periods_source_fact_id",
        "fiscal_periods",
        "financial_facts",
        ["source_fact_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_fiscal_periods_source_fact_id",
        "fiscal_periods",
        ["source_fact_id"],
    )

    op.alter_column(
        "fiscal_periods",
        "derivation_type",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fiscal_periods_source_fact_id",
        table_name="fiscal_periods",
    )

    op.drop_constraint(
        "fk_fiscal_periods_source_fact_id",
        "fiscal_periods",
        type_="foreignkey",
    )

    op.drop_column(
        "fiscal_periods",
        "source_fact_id",
    )

    op.drop_column(
        "fiscal_periods",
        "derivation_type",
    )
