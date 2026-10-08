"""document ownership indexes

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_documents_user_id", "documents", ["user_id"], unique=False)
    op.create_index("uq_documents_user_hash", "documents", ["user_id", "content_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_documents_user_hash", table_name="documents")
    op.drop_index("ix_documents_user_id", table_name="documents")
