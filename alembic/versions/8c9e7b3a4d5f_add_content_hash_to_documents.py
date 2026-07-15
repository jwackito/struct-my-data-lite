"""add content_hash to documents

Revision ID: 8c9e7b3a4d5f
Revises: 6f8e9c2a1b3d
Create Date: 2026-07-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c9e7b3a4d5f"
down_revision: Union[str, None] = "6f8e9c2a1b3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "content_hash")
