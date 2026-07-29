"""Add normalized financial dependencies

Revision ID: dc66fe3b96d4
Revises: f8dd3852468a
Create Date: 2026-07-30 00:37:37.358121

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'dc66fe3b96d4'
down_revision: str | Sequence[str] | None = 'f8dd3852468a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "normalized_financial_dependencies",
        sa.Column(
            "derived_financial_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "source_financial_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "coefficient",
            sa.Numeric(
                precision=12,
                scale=6,
            ),
            nullable=True,
        ),
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=False,
        ),
        sa.CheckConstraint(
            "derived_financial_id <> source_financial_id",
            name=(
                "ck_normalized_financial_dependencies_not_self"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["derived_financial_id"],
            ["normalized_financials.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_financial_id"],
            ["normalized_financials.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "derived_financial_id",
            "source_financial_id",
        ),
    )

    op.create_index(
        "ix_normalized_financial_dependencies_source_financial_id",
        "normalized_financial_dependencies",
        ["source_financial_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_normalized_financial_dependencies_source_financial_id",
        table_name="normalized_financial_dependencies",
    )

    op.drop_table(
        "normalized_financial_dependencies"
    )