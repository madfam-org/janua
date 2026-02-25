"""Add audience column to oauth_clients table

Revision ID: 002
Revises: 001
Create Date: 2026-02-24

Adds per-client JWT audience claim to oauth_clients. When set, tokens minted
for this client carry the client-specific audience instead of the global
JWT_AUDIENCE. Existing clients default to NULL (global audience).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'  # noqa: F841 - Required by Alembic
down_revision: Union[str, None] = '001'  # noqa: F841 - Required by Alembic
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841 - Required by Alembic
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841 - Required by Alembic


def upgrade() -> None:
    op.add_column(
        'oauth_clients',
        sa.Column('audience', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('oauth_clients', 'audience')
