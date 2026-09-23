"""Add email_events: minimized Resend webhook events + per-app feed cursor.

Additive only: one new table, no existing table changes, nothing backfilled.
Re-entrant like 012-017 (checks `inspect()` before every create), because
production applies DDL by hand and this chain must survive an already-present
table. The owner-ready SQL for production is docs/ops/sql/018_email_events.sql
and must stay object-for-object identical to this revision.

Downgrade drops the table. Unlike 017's payment evidence, these rows are
provider telemetry that Resend itself retains and can re-deliver; losing them
costs history, not correctness.
"""

import sqlalchemy as sa

from alembic import op

revision = "018_email_events"
down_revision = "017_payment_mail_dispatch"
branch_labels = None
depends_on = None

TABLE = "email_events"
INDEXES = (
    ("ix_email_events_email_id", ["email_id"]),
    ("ix_email_events_source_app_id", ["source_app", "id"]),
)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        op.create_table(
            TABLE,
            sa.Column(
                "id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                primary_key=True,
                autoincrement=True,
            ),
            sa.Column("provider", sa.String(16), nullable=False, server_default="resend"),
            sa.Column("cuenta", sa.String(32), nullable=False),
            sa.Column("svix_id", sa.String(255), nullable=False),
            sa.Column("email_id", sa.String(255), nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("source_app", sa.String(64), nullable=True),
            sa.Column("org_id", sa.String(64), nullable=True),
            sa.Column("bounce_type", sa.String(64), nullable=True),
            sa.Column("bounce_subtype", sa.String(64), nullable=True),
            sa.Column("click_link", sa.String(2048), nullable=True),
            sa.Column("received_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("svix_id", name="uq_email_events_svix_id"),
        )
        inspector = sa.inspect(bind)
    present = {index["name"] for index in inspector.get_indexes(TABLE)}
    for name, columns in INDEXES:
        if name not in present:
            op.create_index(name, TABLE, columns)


def downgrade():
    bind = op.get_bind()
    if TABLE not in sa.inspect(bind).get_table_names():
        return
    op.drop_table(TABLE)
