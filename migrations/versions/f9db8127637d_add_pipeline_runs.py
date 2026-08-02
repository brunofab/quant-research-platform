"""Add pipeline runs

Revision ID: f9db8127637d
Revises: dc66fe3b96d4
Create Date: 2026-08-02 17:36:24.677204

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f9db8127637d'
down_revision: str | Sequence[str] | None = 'dc66fe3b96d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column(
            "id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "run_type",
            sa.String(length=50),
            nullable=False,
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
            "companies_total",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "companies_succeeded",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "companies_failed",
            sa.Integer(),
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
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ("
            "'running', "
            "'succeeded', "
            "'partial', "
            "'failed'"
            ")",
            name="ck_pipeline_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_pipeline_runs_run_type",
        "pipeline_runs",
        ["run_type"],
    )

    op.create_index(
        "ix_pipeline_runs_status",
        "pipeline_runs",
        ["status"],
    )

    op.create_index(
        "ix_pipeline_runs_started_at",
        "pipeline_runs",
        ["started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pipeline_runs_started_at",
        table_name="pipeline_runs",
    )

    op.drop_index(
        "ix_pipeline_runs_status",
        table_name="pipeline_runs",
    )

    op.drop_index(
        "ix_pipeline_runs_run_type",
        table_name="pipeline_runs",
    )

    op.drop_table("pipeline_runs")