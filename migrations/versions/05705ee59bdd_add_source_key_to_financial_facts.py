"""Add source key to financial facts

Revision ID: 05705ee59bdd
Revises: f631761bcd35
Create Date: 2026-07-29 19:28:26.186094

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '05705ee59bdd'
down_revision: str | Sequence[str] | None = 'f631761bcd35'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_facts",
        sa.Column(
            "source_key",
            sa.String(length=64),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_financial_facts_source_key",
        "financial_facts",
        ["source_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_facts_source_key",
        table_name="financial_facts",
    )

    op.drop_column(
        "financial_facts",
        "source_key",
    )
