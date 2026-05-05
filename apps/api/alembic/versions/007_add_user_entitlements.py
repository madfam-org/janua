"""Add user_entitlements table for Selva-unified SSO Phase 1.

Per-user product:tier grants populated by:
- Dhanam subscription webhooks (subscription.activated|cancelled|updated).
- Admin grants (catch-all for admin@madfam.io).
- Inherited org membership (projected at JWT-issue time, not stored here).

See ADR 2026-05-04-selva-unified-sso (internal-devops) for design rationale.

Revision ID: 007_add_user_entitlements
Revises: 006_add_api_key_rate_limit_and_revoked
Create Date: 2026-05-04
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "007_add_user_entitlements"
down_revision = "006_add_api_key_rate_limit_and_revoked"
branch_labels = None
depends_on = None


_ENTITLEMENT_SOURCE_VALUES = ("dhanam_subscription", "admin_grant", "inherited")


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # PG-native enum where possible; SQLite (used in tests) uses VARCHAR + CHECK.
    if dialect == "postgresql":
        source_type = sa.Enum(
            *_ENTITLEMENT_SOURCE_VALUES,
            name="entitlement_source",
            create_type=True,
        )
    else:
        source_type = sa.String(length=32)

    op.create_table(
        "user_entitlements",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(length=36), nullable=False),
        sa.Column("product", sa.String(length=64), nullable=False),
        sa.Column("tier", sa.String(length=64), nullable=False),
        sa.Column("granted_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("source", source_type, nullable=False),
        sa.Column("dhanam_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "product", name="uq_user_entitlements_user_product"),
    )

    op.create_index(
        "ix_user_entitlements_user_id",
        "user_entitlements",
        ["user_id"],
    )
    op.create_index(
        "ix_user_entitlements_user_expires",
        "user_entitlements",
        ["user_id", "expires_at"],
    )
    op.create_index(
        "ix_user_entitlements_dhanam_subscription_id",
        "user_entitlements",
        ["dhanam_subscription_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.drop_index("ix_user_entitlements_dhanam_subscription_id", table_name="user_entitlements")
    op.drop_index("ix_user_entitlements_user_expires", table_name="user_entitlements")
    op.drop_index("ix_user_entitlements_user_id", table_name="user_entitlements")
    op.drop_table("user_entitlements")

    if dialect == "postgresql":
        sa.Enum(name="entitlement_source").drop(bind, checkfirst=True)
