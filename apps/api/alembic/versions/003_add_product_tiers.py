"""Add product_tiers JSONB column to organizations

Revision ID: 003
Revises: 002
Create Date: 2026-02-27

Adds per-product tier tracking to organizations. Each product (enclii, tezca,
yantra4d, dhanam) can have an independent subscription tier stored in a JSONB
column. The existing subscription_tier column is kept for backwards compatibility
and populated from product_tiers during this migration.
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'organizations',
        sa.Column('product_tiers', JSONB, server_default='{}', nullable=False),
    )

    # Populate product_tiers from existing subscription_tier for enclii
    # Map old Janua tier names to the new unified tier names:
    #   community -> None (not billed, omit from product_tiers)
    #   pro/sovereign -> pro
    #   scale/enterprise -> madfam
    op.execute("""
        UPDATE organizations
        SET product_tiers = jsonb_build_object('enclii', 'pro')
        WHERE subscription_tier IN ('pro', 'sovereign')
    """)
    op.execute("""
        UPDATE organizations
        SET product_tiers = jsonb_build_object('enclii', 'madfam')
        WHERE subscription_tier IN ('scale', 'enterprise')
    """)


def downgrade() -> None:
    op.drop_column('organizations', 'product_tiers')
