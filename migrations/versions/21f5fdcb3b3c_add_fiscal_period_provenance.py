"""Add fiscal period provenance

Revision ID: 21f5fdcb3b3c
Revises: 1d113bfe208f
Create Date: 2026-07-29 22:42:01.623960

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21f5fdcb3b3c'
down_revision: Union[str, Sequence[str], None] = '1d113bfe208f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
