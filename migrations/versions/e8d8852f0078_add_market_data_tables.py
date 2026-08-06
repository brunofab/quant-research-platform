"""Add market data tables

Revision ID: e8d8852f0078
Revises: e0804b723e1a
Create Date: 2026-08-06 20:20:35.915267

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e8d8852f0078'
down_revision: str | Sequence[str] | None = 'e0804b723e1a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_instruments",
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
            "provider",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "provider_symbol",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "exchange",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "mic_code",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=10),
            nullable=False,
        ),
        sa.Column(
            "exchange_timezone",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "asset_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_symbol",
            "mic_code",
            name=(
                "uq_market_instruments_provider_symbol_mic"
            ),
        ),
    )

    op.create_index(
        "ix_market_instruments_company_id",
        "market_instruments",
        ["company_id"],
    )
    op.create_index(
        "ix_market_instruments_provider",
        "market_instruments",
        ["provider"],
    )
    op.create_index(
        "ix_market_instruments_provider_symbol",
        "market_instruments",
        ["provider_symbol"],
    )
    op.create_index(
        "ix_market_instruments_company_provider",
        "market_instruments",
        ["company_id", "provider"],
    )

    op.create_table(
        "market_bars",
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
            "instrument_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "interval",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "bar_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "open_price",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "high_price",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "low_price",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "close_price",
            sa.Numeric(precision=24, scale=8),
            nullable=False,
        ),
        sa.Column(
            "volume",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "currency",
            sa.String(length=10),
            nullable=False,
        ),
        sa.Column(
            "adjustment_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "first_observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "open_price > 0 "
            "AND high_price > 0 "
            "AND low_price > 0 "
            "AND close_price > 0",
            name="ck_market_bars_positive_prices",
        ),
        sa.CheckConstraint(
            "high_price >= open_price "
            "AND high_price >= close_price "
            "AND high_price >= low_price",
            name="ck_market_bars_high_price",
        ),
        sa.CheckConstraint(
            "low_price <= open_price "
            "AND low_price <= close_price "
            "AND low_price <= high_price",
            name="ck_market_bars_low_price",
        ),
        sa.CheckConstraint(
            "volume IS NULL OR volume >= 0",
            name="ck_market_bars_nonnegative_volume",
        ),
        sa.CheckConstraint(
            "last_seen_at >= first_observed_at",
            name="ck_market_bars_observation_order",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["market_instruments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_key",
            name="uq_market_bars_source_key",
        ),
    )

    op.create_index(
        "ix_market_bars_source_key",
        "market_bars",
        ["source_key"],
    )
    op.create_index(
        "ix_market_bars_instrument_id",
        "market_bars",
        ["instrument_id"],
    )
    op.create_index(
        "ix_market_bars_interval",
        "market_bars",
        ["interval"],
    )
    op.create_index(
        "ix_market_bars_bar_date",
        "market_bars",
        ["bar_date"],
    )
    op.create_index(
        "ix_market_bars_instrument_interval_date",
        "market_bars",
        [
            "instrument_id",
            "interval",
            "bar_date",
        ],
    )
    op.create_index(
        "ix_market_bars_instrument_date_seen",
        "market_bars",
        [
            "instrument_id",
            "bar_date",
            "last_seen_at",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_bars_instrument_date_seen",
        table_name="market_bars",
    )
    op.drop_index(
        "ix_market_bars_instrument_interval_date",
        table_name="market_bars",
    )
    op.drop_index(
        "ix_market_bars_bar_date",
        table_name="market_bars",
    )
    op.drop_index(
        "ix_market_bars_interval",
        table_name="market_bars",
    )
    op.drop_index(
        "ix_market_bars_instrument_id",
        table_name="market_bars",
    )
    op.drop_index(
        "ix_market_bars_source_key",
        table_name="market_bars",
    )
    op.drop_table("market_bars")

    op.drop_index(
        "ix_market_instruments_company_provider",
        table_name="market_instruments",
    )
    op.drop_index(
        "ix_market_instruments_provider_symbol",
        table_name="market_instruments",
    )
    op.drop_index(
        "ix_market_instruments_provider",
        table_name="market_instruments",
    )
    op.drop_index(
        "ix_market_instruments_company_id",
        table_name="market_instruments",
    )
    op.drop_table("market_instruments")