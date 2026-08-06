"""Add pipeline step results

Revision ID: e86c6dcb6286
Revises: e8d8852f0078
Create Date: 2026-08-06 21:41:23.838768

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e86c6dcb6286'
down_revision: str | Sequence[str] | None = 'e8d8852f0078'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_step_results",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "pipeline_run_id",
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
            "step_name",
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
            "records_received",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "records_inserted",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "records_seen_again",
            sa.BigInteger(),
            server_default="0",
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
            "context_json",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ("
            "'succeeded', "
            "'failed', "
            "'skipped'"
            ")",
            name="ck_pipeline_step_results_status",
        ),
        sa.CheckConstraint(
            "execution_order >= 1 "
            "AND records_received >= 0 "
            "AND records_inserted >= 0 "
            "AND records_seen_again >= 0 "
            "AND duration_ms >= 0",
            name="ck_pipeline_step_results_counts",
        ),
        sa.CheckConstraint(
            "finished_at >= started_at",
            name=(
                "ck_pipeline_step_results_time_order"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pipeline_run_id",
            "scope_type",
            "scope_key",
            "step_name",
            name="uq_pipeline_step_results_identity",
        ),
    )

    op.create_index(
        "ix_pipeline_step_results_pipeline_run_id",
        "pipeline_step_results",
        ["pipeline_run_id"],
    )

    op.create_index(
        "ix_pipeline_step_results_run_status",
        "pipeline_step_results",
        ["pipeline_run_id", "status"],
    )

    op.create_index(
        "ix_pipeline_step_results_run_step",
        "pipeline_step_results",
        ["pipeline_run_id", "step_name"],
    )

    op.create_index(
        "ix_pipeline_step_results_company_id",
        "pipeline_step_results",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pipeline_step_results_company_id",
        table_name="pipeline_step_results",
    )

    op.drop_index(
        "ix_pipeline_step_results_run_step",
        table_name="pipeline_step_results",
    )

    op.drop_index(
        "ix_pipeline_step_results_run_status",
        table_name="pipeline_step_results",
    )

    op.drop_index(
        "ix_pipeline_step_results_pipeline_run_id",
        table_name="pipeline_step_results",
    )

    op.drop_table("pipeline_step_results")
