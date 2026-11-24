"""Create device_clients and device_enrolments — shared devices as OAuth clients.

WHY. A shared shop-floor terminal is enrolled as a confidential OAuth client of
kind ``device`` (`app/core/device_clients.py`): it generates its own secret,
sends it once, shows a short code, and an administrator of its organization
approves the code. Janua then creates the device's client from a
platform-defined template. ``device_clients`` is the device's identity record
(organization, template, state, who approved or disabled it, its last token and
its boot-identifier signal); ``device_enrolments`` holds a request until a
person approves it or it expires. See `app/models/device_client.py`.

WHY TABLES, NOT A COLUMN ON `oauth_clients`. ``oauth_clients`` is read on every
token request; a column there would make any image carrying it refuse every
client on a database without this migration. These tables are read only for a
device client (recognized by its ``client_id`` prefix) and by the enrolment
routes, so the image and this migration can ship in either order. Without the
tables the enrolment routes fail and no device can exist; nothing else changes.

SHAPE.
- ``device_clients``: ``id`` PK; ``oauth_client_id`` UNIQUE -> oauth_clients ON
  DELETE CASCADE; ``organization_id`` -> organizations ON DELETE CASCADE;
  ``approved_by`` / ``disabled_by`` -> users ON DELETE SET NULL;
  ``boot_alternations`` defaults to 0. Index on ``organization_id``.
- ``device_enrolments``: ``id`` PK; ``user_code`` UNIQUE; ``organization_id``
  -> organizations ON DELETE CASCADE; ``replaces_device_id`` / ``device_id`` ->
  device_clients ON DELETE SET NULL; ``approved_by`` -> users ON DELETE SET NULL.
  Index on ``(organization_id, status)``.

ADDITIVE. Two new, empty tables. No existing table, column, index or grant
changes.

DEPLOY NOTE (operator step, not automatic): promote runs no migrations, and the
staging overlay sets `JANUA_APPLY_MIGRATIONS=false`. The reviewed operator SQL
is `docs/ops/sql/023_device_clients.sql`, object-for-object the same as this
file (parity tested in `tests/unit/test_device_clients_postgres.py`).

RE-ENTRANT ON PURPOSE, like 016, 021 and 022: environments built with
`Base.metadata.create_all` already carry the tables while `alembic_version`
reads an older revision.

Revision ID: 023_device_clients
Revises: 022_user_primary_organization
Create Date: 2026-11-20
"""

import sqlalchemy as sa

from alembic import op

# Constraint names are explicit (they equal what the naming convention in
# app/core/database.py would produce) so the operator SQL can name them too.
# Keep revision ids <= 32 characters: `alembic_version.version_num` is
# VARCHAR(32). Enforced by tests/unit/test_alembic_revision_graph.py.
revision = "023_device_clients"
down_revision = "022_user_primary_organization"
branch_labels = None
depends_on = None

DEVICES = "device_clients"
ENROLMENTS = "device_enrolments"
DEVICES_ORGANIZATION_INDEX = "ix_device_clients_organization_id"
ENROLMENTS_ORGANIZATION_INDEX = "ix_device_enrolments_organization_id_status"


def _users_fk(table: str, column: str) -> sa.ForeignKey:
    return sa.ForeignKey("users.id", ondelete="SET NULL", name=f"fk_{table}_{column}_users")


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if DEVICES not in tables:
        op.create_table(
            DEVICES,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column(
                "oauth_client_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "oauth_clients.id",
                    ondelete="CASCADE",
                    name="fk_device_clients_oauth_client_id_oauth_clients",
                ),
                nullable=False,
            ),
            sa.Column(
                "organization_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "organizations.id",
                    ondelete="CASCADE",
                    name="fk_device_clients_organization_id_organizations",
                ),
                nullable=False,
            ),
            sa.Column("template", sa.String(64), nullable=False),
            sa.Column("label", sa.String(100), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("approved_by", sa.Uuid(), _users_fk(DEVICES, "approved_by"), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=False),
            sa.Column("disabled_by", sa.Uuid(), _users_fk(DEVICES, "disabled_by"), nullable=True),
            sa.Column("disabled_at", sa.DateTime(), nullable=True),
            sa.Column("disabled_reason", sa.String(300), nullable=True),
            sa.Column("last_token_at", sa.DateTime(), nullable=True),
            sa.Column("recent_boot_ids", sa.String(400), nullable=True),
            sa.Column(
                "boot_alternations", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column("clone_suspected_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_device_clients"),
            sa.UniqueConstraint("oauth_client_id", name="uq_device_clients_oauth_client_id"),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes(DEVICES)}
    if DEVICES_ORGANIZATION_INDEX not in indexes:
        op.create_index(DEVICES_ORGANIZATION_INDEX, DEVICES, ["organization_id"])

    if ENROLMENTS not in tables:
        op.create_table(
            ENROLMENTS,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column(
                "organization_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "organizations.id",
                    ondelete="CASCADE",
                    name="fk_device_enrolments_organization_id_organizations",
                ),
                nullable=False,
            ),
            sa.Column("template", sa.String(64), nullable=False),
            sa.Column("label", sa.String(100), nullable=False),
            sa.Column("user_code", sa.String(9), nullable=False),
            sa.Column("secret_hash", sa.String(255), nullable=True),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column(
                "replaces_device_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "device_clients.id",
                    ondelete="SET NULL",
                    name="fk_device_enrolments_replaces_device_id_device_clients",
                ),
                nullable=True,
            ),
            sa.Column("requested_ip", sa.String(64), nullable=True),
            sa.Column("requested_user_agent", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column(
                "approved_by", sa.Uuid(), _users_fk(ENROLMENTS, "approved_by"), nullable=True
            ),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column(
                "device_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "device_clients.id",
                    ondelete="SET NULL",
                    name="fk_device_enrolments_device_id_device_clients",
                ),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id", name="pk_device_enrolments"),
            sa.UniqueConstraint("user_code", name="uq_device_enrolments_user_code"),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes(ENROLMENTS)}
    if ENROLMENTS_ORGANIZATION_INDEX not in indexes:
        op.create_index(ENROLMENTS_ORGANIZATION_INDEX, ENROLMENTS, ["organization_id", "status"])


def downgrade() -> None:
    # Dropping the tables forgets every enrolled device's record. Their OAuth
    # clients stay on oauth_clients, and the token endpoint refuses them (it
    # issues a device client nothing without its record), so every device must
    # enrol again after an upgrade. Acceptable only as the inverse of this
    # forward migration.
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if ENROLMENTS in tables:
        op.drop_table(ENROLMENTS)
    if DEVICES in tables:
        op.drop_table(DEVICES)
