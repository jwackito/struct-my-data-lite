"""add extraction_jobs.error_detail

Revision ID: e1f2a3b4c5d6
Revises: c9d8e7f6a5b4
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'c9d8e7f6a5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'extraction_jobs',
        sa.Column('error_detail', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('extraction_jobs', 'error_detail')
