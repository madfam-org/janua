"""Set per-client JWT audience for tezca-web OAuth client.

The audience column was added in migration 002 but left NULL for existing
clients. This data migration populates it so Janua issues tokens with
aud='tezca-api' instead of falling back to the global default 'janua.dev'.

Revision ID: 005_set_tezca_client_audience
Revises: 004_add_guest_invites
Create Date: 2026-03-16
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "005_set_tezca_client_audience"
down_revision = "004_add_guest_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE oauth_clients SET audience = 'tezca-api' WHERE name = 'tezca-web'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE oauth_clients SET audience = NULL WHERE name = 'tezca-web'"
    )
