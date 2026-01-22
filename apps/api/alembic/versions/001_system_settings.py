"""Add system_settings and allowed_cors_origins tables

Revision ID: 001
Revises: 000
Create Date: 2026-01-20

This migration adds dynamic system settings management:
- system_settings: Key-value store for platform configuration
- allowed_cors_origins: Multi-tenant CORS origin management
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'  # noqa: F841 - Required by Alembic
down_revision: Union[str, None] = '000'  # noqa: F841 - Required by Alembic
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841 - Required by Alembic
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841 - Required by Alembic


def upgrade() -> None:
    # === System Settings Table ===
    op.create_table('system_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('json_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='features'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_sensitive', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_readonly', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_settings_key'), 'system_settings', ['key'], unique=True)
    op.create_index(op.f('ix_system_settings_category'), 'system_settings', ['category'], unique=False)

    # === Allowed CORS Origins Table ===
    op.create_table('allowed_cors_origins',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('origin', sa.String(length=500), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_allowed_cors_origins_active'), 'allowed_cors_origins', ['is_active'], unique=False)
    op.create_index(op.f('ix_allowed_cors_origins_org'), 'allowed_cors_origins', ['organization_id'], unique=False)
    # Unique constraint: origin must be unique per organization (or globally for system-level)
    op.create_index(
        'ix_allowed_cors_origins_unique',
        'allowed_cors_origins',
        ['origin', 'organization_id'],
        unique=True
    )


def downgrade() -> None:
    # Drop allowed_cors_origins
    op.drop_index('ix_allowed_cors_origins_unique', table_name='allowed_cors_origins')
    op.drop_index(op.f('ix_allowed_cors_origins_org'), table_name='allowed_cors_origins')
    op.drop_index(op.f('ix_allowed_cors_origins_active'), table_name='allowed_cors_origins')
    op.drop_table('allowed_cors_origins')

    # Drop system_settings
    op.drop_index(op.f('ix_system_settings_category'), table_name='system_settings')
    op.drop_index(op.f('ix_system_settings_key'), table_name='system_settings')
    op.drop_table('system_settings')
