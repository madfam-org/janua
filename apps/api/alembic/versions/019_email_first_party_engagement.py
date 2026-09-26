"""First-party email engagement: email_events.source + possible_prefetch, email_tracking_links.

Additive only. `email_events` gains two columns: `source` (NOT NULL, default
'webhook', so every existing row reads as what it is) and `possible_prefetch`
(nullable). A new table `email_tracking_links` holds one row per instrumented
message: the SHA-256 of its opaque token, the Resend account and tags, the
Resend `email_id` once bound, and the ORIGINAL link targets (JSON text) the
click redirect reads by index. See app/services/email_engagement.py.

Re-entrant like 012-018 (checks `inspect()` before every change), because
production applies DDL by hand. The owner-ready SQL for production is
docs/ops/sql/019_email_first_party_engagement.sql and must stay object-for-object
identical to this revision (tests/unit/test_email_engagement_migration.py).

Downgrade drops the table and the two columns. First-party events already in
`email_events` stay (as rows the old code reads as webhook events of type
opened/clicked); losing the token table only makes old tracking links fall back
to the tenant's default site.
"""

import sqlalchemy as sa

from alembic import op

revision = "019_email_first_party_engagement"
down_revision = "018_email_events"
branch_labels = None
depends_on = None

EVENTS = "email_events"
LINKS = "email_tracking_links"
LINKS_INDEX = ("ix_email_tracking_links_email_id", ["email_id"])


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(EVENTS)}
    if "source" not in columns:
        op.add_column(
            EVENTS,
            sa.Column("source", sa.String(16), nullable=False, server_default="webhook"),
        )
    if "possible_prefetch" not in columns:
        op.add_column(EVENTS, sa.Column("possible_prefetch", sa.Boolean(), nullable=True))

    if LINKS not in inspector.get_table_names():
        op.create_table(
            LINKS,
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("cuenta", sa.String(32), nullable=False),
            sa.Column("source_app", sa.String(64), nullable=True),
            sa.Column("org_id", sa.String(64), nullable=True),
            sa.Column("email_id", sa.String(255), nullable=True),
            sa.Column("links", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("token_hash", name="pk_email_tracking_links"),
        )
    inspector = sa.inspect(bind)
    present = {index["name"] for index in inspector.get_indexes(LINKS)}
    name, cols = LINKS_INDEX
    if name not in present:
        op.create_index(name, LINKS, cols)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if LINKS in inspector.get_table_names():
        op.drop_table(LINKS)
    columns = {column["name"] for column in inspector.get_columns(EVENTS)}
    if "possible_prefetch" in columns:
        op.drop_column(EVENTS, "possible_prefetch")
    if "source" in columns:
        op.drop_column(EVENTS, "source")
