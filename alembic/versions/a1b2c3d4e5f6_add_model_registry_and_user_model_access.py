"""model registry and user model access

Revision ID: a1b2c3d4e5f6
Revises: 3eaabd98448f
Create Date: 2026-09-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3eaabd98448f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('model_registry',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('connection_id', sa.Uuid(), nullable=False),
    sa.Column('model_name', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('capabilities', sa.JSON(), nullable=True),
    sa.Column('context_window', sa.Integer(), nullable=True),
    sa.Column('price_input_usd', sa.Float(), nullable=True),
    sa.Column('price_output_usd', sa.Float(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('admin_only', sa.Boolean(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['connection_id'], ['llm_connections.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('connection_id', 'model_name', name='uq_model_registry_connection_model')
    )
    op.create_index('ix_model_registry_connection_id', 'model_registry', ['connection_id'], unique=False)
    op.create_index('ix_model_registry_one_default', 'model_registry', ['connection_id'], unique=True, postgresql_where=sa.text('is_default'))
    op.create_table('user_model_access',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('model_id', sa.Uuid(), nullable=False),
    sa.Column('access', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['model_id'], ['model_registry.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'model_id', name='uq_user_model_access_user_model')
    )
    op.create_index('ix_user_model_access_model_id', 'user_model_access', ['model_id'], unique=False)
    op.create_index('ix_user_model_access_user_id', 'user_model_access', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_user_model_access_user_id', table_name='user_model_access')
    op.drop_index('ix_user_model_access_model_id', table_name='user_model_access')
    op.drop_table('user_model_access')
    op.drop_index('ix_model_registry_one_default', table_name='model_registry')
    op.drop_index('ix_model_registry_connection_id', table_name='model_registry')
    op.drop_table('model_registry')