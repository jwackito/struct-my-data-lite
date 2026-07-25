"""add provider_name and model_name to extraction jobs

Revision ID: 94fb4b26a6c6
Revises: 826ce723b633
Create Date: 2026-07-25 14:37:49.526377

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94fb4b26a6c6'
down_revision: Union[str, None] = '826ce723b633'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('extraction_jobs', sa.Column('provider_name', sa.String(length=50), nullable=True))
    op.add_column('extraction_jobs', sa.Column('model_name', sa.String(length=100), nullable=True))
    op.execute("UPDATE extraction_jobs SET provider_name = 'ollama' WHERE provider_name IS NULL")
    op.alter_column('extraction_jobs', 'provider_name', nullable=False)


def downgrade() -> None:
    op.drop_column('extraction_jobs', 'model_name')
    op.drop_column('extraction_jobs', 'provider_name')
