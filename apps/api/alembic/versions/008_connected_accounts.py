"""Add connected_accounts and provider_types for Coupler P1 (ADR-002).

Revision ID: 008_connected_accounts
Revises: 007_add_user_entitlements
Create Date: 2026-06-19
"""

import sqlalchemy as sa
from alembic import op

revision = "008_connected_accounts"
down_revision = "007_add_user_entitlements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = sa.dialects.postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    json_type = sa.JSON() if dialect == "sqlite" else sa.dialects.postgresql.JSONB()

    op.create_table(
        "provider_types",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("type_code", sa.String(50), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="integration"),
        sa.Column("supports_oauth", sa.String(5), server_default="true"),
        sa.Column("is_active", sa.String(5), server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "connected_accounts",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", uuid_type, sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column("provider_id", sa.String(255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("oauth_scopes", json_type, nullable=True),
        sa.Column("oauth_expires_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("metadata", json_type, nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", uuid_type, sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_connected_accounts_user_id", "connected_accounts", ["user_id"])
    op.create_index("ix_connected_accounts_provider_type", "connected_accounts", ["provider_type"])

    op.bulk_insert(
        sa.table(
            "provider_types",
            sa.column("id", uuid_type),
            sa.column("type_code", sa.String),
            sa.column("display_name", sa.String),
            sa.column("category", sa.String),
            sa.column("supports_oauth", sa.String),
            sa.column("is_active", sa.String),
        ),
        [
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "type_code": "github",
                "display_name": "GitHub",
                "category": "development",
                "supports_oauth": "true",
                "is_active": "true",
            },
            {
                "id": "00000000-0000-4000-8000-000000000002",
                "type_code": "slack",
                "display_name": "Slack",
                "category": "communication",
                "supports_oauth": "true",
                "is_active": "true",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_connected_accounts_provider_type", table_name="connected_accounts")
    op.drop_index("ix_connected_accounts_user_id", table_name="connected_accounts")
    op.drop_table("connected_accounts")
    op.drop_table("provider_types")
