"""add saved_schemas.is_public and unique user/name index

Revision ID: c9d8e7f6a5b4
Revises: a1b2c3d4e5f6
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d8e7f6a5b4'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'saved_schemas',
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.create_index(
        'uq_saved_schemas_user_name',
        'saved_schemas',
        ['user_id', 'name'],
        unique=True,
        postgresql_where=sa.text('user_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_saved_schemas_user_name', table_name='saved_schemas')
    op.drop_column('saved_schemas', 'is_public')
