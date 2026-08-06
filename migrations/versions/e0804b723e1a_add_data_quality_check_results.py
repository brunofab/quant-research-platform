"""Add data quality check results

Revision ID: e0804b723e1a
Revises: 6a794d4584a0
Create Date: 2026-08-06 12:30:14.290193

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e0804b723e1a'
down_revision: str | Sequence[str] | None = '6a794d4584a0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_quality_check_results",
        sa.Column(
            "id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "data_quality_run_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "scope_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "scope_key",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "dataset",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "check_name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "execution_order",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "records_checked",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "issues_found",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "blocking_issues",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "status IN "
                "('passed', 'warning', 'failed')"
            ),
            name=(
                "ck_data_quality_check_results_status"
            ),
        ),
        sa.CheckConstraint(
            (
                "execution_order >= 1 "
                "AND records_checked >= 0 "
                "AND issues_found >= 0 "
                "AND blocking_issues >= 0 "
                "AND blocking_issues <= issues_found "
                "AND duration_ms >= 0"
            ),
            name=(
                "ck_data_quality_check_results_counts"
            ),
        ),
        sa.CheckConstraint(
            "finished_at >= started_at",
            name=(
                "ck_data_quality_check_results_time_order"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["data_quality_run_id"],
            ["data_quality_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "data_quality_run_id",
            "scope_type",
            "scope_key",
            "dataset",
            "check_name",
            name=(
                "uq_data_quality_check_results_identity"
            ),
        ),
    )

    op.create_index(
        "ix_data_quality_check_results_company_id",
        "data_quality_check_results",
        ["company_id"],
    )

    op.create_index(
        "ix_data_quality_check_results_run_check",
        "data_quality_check_results",
        [
            "data_quality_run_id",
            "check_name",
        ],
    )

    op.create_index(
        "ix_data_quality_check_results_run_status",
        "data_quality_check_results",
        [
            "data_quality_run_id",
            "status",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_quality_check_results_run_status",
        table_name="data_quality_check_results",
    )

    op.drop_index(
        "ix_data_quality_check_results_run_check",
        table_name="data_quality_check_results",
    )

    op.drop_index(
        "ix_data_quality_check_results_company_id",
        table_name="data_quality_check_results",
    )

    op.drop_table(
        "data_quality_check_results"
    )
