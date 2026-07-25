"""add llm_connections, rename provider_name to connection_name

Revision ID: 34a8511c3f85
Revises: 94fb4b26a6c6
Create Date: 2026-07-25 15:25:35.911575

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '34a8511c3f85'
down_revision: Union[str, None] = '94fb4b26a6c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('llm_connections',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('config', sa.JSON(), nullable=False),
    sa.Column('secrets', sa.Text(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.alter_column('extraction_jobs', 'provider_name', new_column_name='connection_name')
    op.alter_column('extraction_jobs', 'connection_name', type_=sa.String(100), existing_type=sa.String(50))
    op.add_column('extraction_jobs', sa.Column('provider_type', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('extraction_jobs', 'provider_type')
    op.alter_column('extraction_jobs', 'connection_name', new_column_name='provider_name')
    op.alter_column('extraction_jobs', 'provider_name', type_=sa.String(50), existing_type=sa.String(100))
    op.drop_table('llm_connections')
