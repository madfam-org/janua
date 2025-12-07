"""add oauth_clients table

Revision ID: 010
Revises: 009
Create Date: 2025-12-06 10:00:00.000000

This migration adds the oauth_clients table for OAuth2 client registration.
This enables external applications (like Enclii) to use Janua as an OAuth Provider.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create oauth_clients table for OAuth2 Provider functionality."""

    # Create oauth_clients table
    op.create_table(
        "oauth_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Client credentials
        sa.Column("client_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("client_secret_hash", sa.String(255), nullable=False),
        sa.Column("client_secret_prefix", sa.String(20), nullable=False),
        # Configuration
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "redirect_uris",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "allowed_scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='["openid", "profile", "email"]',
        ),
        sa.Column(
            "grant_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='["authorization_code", "refresh_token"]',
        ),
        # Metadata
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("website_url", sa.String(500), nullable=True),
        # Status
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_confidential", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create indexes for common queries
    op.create_index(
        "ix_oauth_clients_organization_id",
        "oauth_clients",
        ["organization_id"],
    )
    op.create_index(
        "ix_oauth_clients_created_by",
        "oauth_clients",
        ["created_by"],
    )
    op.create_index(
        "ix_oauth_clients_is_active",
        "oauth_clients",
        ["is_active"],
    )

    # Grant permissions to janua user
    op.execute("GRANT ALL PRIVILEGES ON TABLE oauth_clients TO janua;")


def downgrade() -> None:
    """Remove oauth_clients table."""
    op.drop_index("ix_oauth_clients_is_active", table_name="oauth_clients")
    op.drop_index("ix_oauth_clients_created_by", table_name="oauth_clients")
    op.drop_index("ix_oauth_clients_organization_id", table_name="oauth_clients")
    op.drop_table("oauth_clients")
