"""Add generic data quality tables

Revision ID: 6a794d4584a0
Revises: f9db8127637d
Create Date: 2026-08-03 19:03:07.600411

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6a794d4584a0'
down_revision: str | Sequence[str] | None = 'f9db8127637d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_quality_runs",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "pipeline_run_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "dataset",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "scope_type",
            sa.String(length=50),
            server_default="global",
            nullable=False,
        ),
        sa.Column(
            "scope_key",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="running",
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "checks_executed",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "records_checked",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "issues_found",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "blocking_issues",
            sa.Integer(),
            server_default="0",
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
        sa.CheckConstraint(
            "status IN ("
            "'running', "
            "'passed', "
            "'warning', "
            "'failed'"
            ")",
            name="ck_data_quality_runs_status",
        ),
        sa.CheckConstraint(
            "checks_executed >= 0 AND "
            "records_checked >= 0 AND "
            "issues_found >= 0 AND "
            "blocking_issues >= 0 AND "
            "blocking_issues <= issues_found",
            name=(
                "ck_data_quality_runs_"
                "nonnegative_counts"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"],
            ["pipeline_runs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_data_quality_runs_pipeline_run_id",
        "data_quality_runs",
        ["pipeline_run_id"],
    )

    op.create_index(
        "ix_data_quality_runs_dataset_started_at",
        "data_quality_runs",
        ["dataset", "started_at"],
    )

    op.create_index(
        "ix_data_quality_runs_pipeline_status",
        "data_quality_runs",
        ["pipeline_run_id", "status"],
    )

    op.create_table(
        "data_quality_issues",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
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
            "entity_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "entity_key",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "dataset",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "metric",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "check_name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "blocking",
            sa.Boolean(),
            server_default=sa.text("false"),
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
            nullable=True,
        ),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "actual_value",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "expected_value",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "context_json",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ("
            "'info', "
            "'warning', "
            "'error', "
            "'critical'"
            ")",
            name="ck_data_quality_issues_severity",
        ),
        sa.CheckConstraint(
            "period_start IS NULL OR "
            "period_end IS NULL OR "
            "period_start <= period_end",
            name="ck_data_quality_issues_period_order",
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
    )

    op.create_index(
        "ix_data_quality_issues_data_quality_run_id",
        "data_quality_issues",
        ["data_quality_run_id"],
    )

    op.create_index(
        "ix_data_quality_issues_company_id",
        "data_quality_issues",
        ["company_id"],
    )

    op.create_index(
        "ix_data_quality_issues_run_severity",
        "data_quality_issues",
        ["data_quality_run_id", "severity"],
    )

    op.create_index(
        "ix_data_quality_issues_entity",
        "data_quality_issues",
        ["entity_type", "entity_key"],
    )

    op.create_index(
        "ix_data_quality_issues_dataset_check",
        "data_quality_issues",
        ["dataset", "check_name"],
    )

    op.create_index(
        "ix_data_quality_issues_company_period",
        "data_quality_issues",
        ["company_id", "period_end"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_quality_issues_company_period",
        table_name="data_quality_issues",
    )

    op.drop_index(
        "ix_data_quality_issues_dataset_check",
        table_name="data_quality_issues",
    )

    op.drop_index(
        "ix_data_quality_issues_entity",
        table_name="data_quality_issues",
    )

    op.drop_index(
        "ix_data_quality_issues_run_severity",
        table_name="data_quality_issues",
    )

    op.drop_index(
        "ix_data_quality_issues_company_id",
        table_name="data_quality_issues",
    )

    op.drop_index(
        "ix_data_quality_issues_data_quality_run_id",
        table_name="data_quality_issues",
    )

    op.drop_table("data_quality_issues")

    op.drop_index(
        "ix_data_quality_runs_pipeline_status",
        table_name="data_quality_runs",
    )

    op.drop_index(
        "ix_data_quality_runs_dataset_started_at",
        table_name="data_quality_runs",
    )

    op.drop_index(
        "ix_data_quality_runs_pipeline_run_id",
        table_name="data_quality_runs",
    )

    op.drop_table("data_quality_runs")
