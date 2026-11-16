"""Add users.primary_organization_id — an operator-set primary organization.

WHY. The organization claims resolver (`app/services/org_claims_service.py`)
emits `org_id`, `madfam_org_roles` and application roles (`roles`) only for an
UNAMBIGUOUS primary membership: exactly one active membership, or
`users.tenant_id` naming one of them. A staff account with several active
memberships and `tenant_id` NULL therefore gets `orgs` and nothing else, so it
can never pass a resource server that gates on an application role.

`tenant_id` cannot be the answer. It is the email-uniqueness pool the identity
lives in (migration 013, and the docstring of
`app/routers/v1/internal_users.py`): setting it on staff once made magic link
and password reset unable to find them. Identity pool and primary organization
are two different facts, so this is a second column, not a second meaning for
the first one.

The resolver still refuses to GUESS a primary organization. This column is the
EXPLICIT one, written only by an operator through the internal API
(`app/routers/v1/internal_primary_organization.py`), and it counts only while
the user holds an ACTIVE membership in that organization.

SHAPE. Nullable UUID, foreign key to `organizations.id` ON DELETE SET NULL:
deleting an organization clears the pointer instead of blocking the delete or
leaving a dangling id. NULL — every existing row — is today's behaviour exactly.
No index: the column is read through the user row the resolver already holds,
and organizations are deleted rarely enough that the SET NULL scan of `users`
does not justify a new index on a hot table.

NON-DESTRUCTIVE AND ADDITIVE. One nullable column without a default (a
catalog-only change on PostgreSQL) and one foreign key over a column that is
NULL everywhere, so validating it reads nothing it could reject. No existing
column, index or grant changes.

DEPLOY NOTE (operator step, not automatic): `promote` runs NO migrations in
this ecosystem, and the staging overlay sets `JANUA_APPLY_MIGRATIONS=false`.
The reviewed operator SQL is `docs/ops/sql/022_user_primary_organization.sql`
(object-for-object the same as this file; parity is tested in
`tests/unit/test_user_primary_organization_postgres.py`). Apply it BEFORE any
image carrying this revision runs against a database: the ORM selects and
inserts the column on every `User` read and write, so an image that meets a
database without it fails loudly on login — the intended failure, not a silent
wrong answer — exactly as 015 (`users.is_service_account`) did.

RE-ENTRANT ON PURPOSE, matching 015 and 021: environments built with
`Base.metadata.create_all` already carry the column while `alembic_version`
reads an older revision, and an unguarded add_column there raises
DuplicateColumn and rolls back the WHOLE chain.

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

COLUMN = "primary_organization_id"
FOREIGN_KEY = "fk_users_primary_organization_id"


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("users")}
    if COLUMN not in columns:
        op.add_column("users", sa.Column(COLUMN, sa.Uuid(), nullable=True))

    # PostgreSQL only, like 021: SQLite cannot ALTER TABLE ... ADD CONSTRAINT,
    # and the test suite's SQLite schema comes from the models anyway.
    if bind.dialect.name == "postgresql":
        foreign_keys = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys("users")}
        if FOREIGN_KEY not in foreign_keys:
            op.create_foreign_key(
                FOREIGN_KEY,
                "users",
                "organizations",
                [COLUMN],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        foreign_keys = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys("users")}
        if FOREIGN_KEY in foreign_keys:
            op.drop_constraint(FOREIGN_KEY, "users", type_="foreignkey")
    columns = {c["name"] for c in sa.inspect(bind).get_columns("users")}
    if COLUMN in columns:
        op.drop_column("users", COLUMN)
