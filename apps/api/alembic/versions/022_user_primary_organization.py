"""Create user_primary_organizations — an operator-set primary organization.

WHY. The organization claims resolver (`app/services/org_claims_service.py`)
emits `org_id`, `madfam_org_roles` and application roles (`roles`) only for an
UNAMBIGUOUS primary membership: exactly one active membership, or
`users.tenant_id` naming one of them. A staff account with several active
memberships and `tenant_id` NULL therefore gets `orgs` and nothing else, so it
can never pass a resource server that gates on an application role.

`tenant_id` cannot be the answer: it is the email-uniqueness pool the identity
lives in (migration 013, `app/routers/v1/internal_users.py`), and setting it on
staff once made magic link and password reset unable to find them.

The resolver still refuses to GUESS. This table holds the EXPLICIT choice,
written only by an operator through the internal API
(`app/routers/v1/internal_primary_organization.py`), and it counts only while
the user holds an ACTIVE membership in that organization.

WHY A TABLE, NOT A COLUMN ON `users`. The `User` model is read on every login,
so a column there would make any image that carries it fail every login on a
database without the migration. This table is read only by the resolver, in a
guarded read that degrades to "no primary" on any failure (missing table
included), like `organization_member_app_roles` (016). The image and this
migration can therefore ship in either order without affecting availability.

SHAPE. `user_id` PK -> users ON DELETE CASCADE (one pointer per person);
`organization_id` -> organizations ON DELETE CASCADE (a deleted organization
means no primary), nullable because clearing is an UPDATE to NULL, not a
DELETE; `set_by` / `set_at` record who last wrote it. One index on
`organization_id` for the cascade.

ADDITIVE. A new, empty table. No existing table, column, index or grant
changes.

DEPLOY NOTE (operator step, not automatic): promote runs no migrations, and the
staging overlay sets `JANUA_APPLY_MIGRATIONS=false`. The reviewed operator SQL
is `docs/ops/sql/022_user_primary_organization.sql`, object-for-object the same
as this file (parity tested in
`tests/unit/test_user_primary_organization_postgres.py`).

RE-ENTRANT ON PURPOSE, like 016 and 021: environments built with
`Base.metadata.create_all` already carry the table while `alembic_version`
reads an older revision.

Revision ID: 022_user_primary_organization
Revises: 021_map_email_traceability
Create Date: 2026-11-16
"""

import sqlalchemy as sa

from alembic import op

# Keep revision ids <= 32 characters: `alembic_version.version_num` is
# VARCHAR(32). Enforced by tests/unit/test_alembic_revision_graph.py.
revision = "022_user_primary_organization"
down_revision = "021_map_email_traceability"
branch_labels = None
depends_on = None

TABLE = "user_primary_organizations"
ORGANIZATION_INDEX = "ix_user_primary_organizations_organization_id"


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE not in sa.inspect(bind).get_table_names():
        op.create_table(
            TABLE,
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "organization_id",
                sa.Uuid(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("set_by", sa.String(255), nullable=False),
            sa.Column("set_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("user_id", name="pk_user_primary_organizations"),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes(TABLE)}
    if ORGANIZATION_INDEX not in indexes:
        op.create_index(ORGANIZATION_INDEX, TABLE, ["organization_id"])


def downgrade() -> None:
    # Dropping the table discards operators' current choices; their history is
    # on the AuditLogger trail. Acceptable only as the inverse of this forward
    # migration.
    bind = op.get_bind()
    if TABLE in sa.inspect(bind).get_table_names():
        op.drop_table(TABLE)
