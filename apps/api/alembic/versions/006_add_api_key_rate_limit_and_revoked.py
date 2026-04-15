"""Add rate_limit_per_min, revoked_at, and key_prefix columns to api_keys table.

These columns support the new API key management features:
- rate_limit_per_min: per-key rate limiting (default 60 req/min)
- revoked_at: explicit revocation timestamp (supplements is_active flag)
- key_prefix: visible prefix like "sk_live_ab3f" for key identification

Revision ID: 006_add_api_key_rate_limit_and_revoked
Revises: 005_set_tezca_client_audience
Create Date: 2026-04-15
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "006_add_api_key_rate_limit_and_revoked"
down_revision = "005_set_tezca_client_audience"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add rate_limit_per_min with a sensible default
    op.add_column(
        "api_keys",
        sa.Column("rate_limit_per_min", sa.Integer(), nullable=True, server_default="60"),
    )
    # Add revoked_at timestamp (nullable -- NULL means not revoked)
    op.add_column(
        "api_keys",
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    # Add key_prefix for visible short prefix (e.g. "sk_live_ab3f")
    op.add_column(
        "api_keys",
        sa.Column("key_prefix", sa.String(length=12), nullable=True),
    )

    # Backfill revoked_at for already-revoked keys (is_active=false)
    op.execute(
        "UPDATE api_keys SET revoked_at = updated_at WHERE is_active = false AND revoked_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("api_keys", "key_prefix")
    op.drop_column("api_keys", "revoked_at")
    op.drop_column("api_keys", "rate_limit_per_min")
