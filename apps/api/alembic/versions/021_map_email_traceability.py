"""Write-ahead MAP mail receipts and verified event correlation; no backfill.

Apply before the application image. Downgrade retains intent/receipt evidence.
"""

import sqlalchemy as sa

from alembic import op

revision = "021_map_email_traceability"
down_revision = "020_org_authentication_policy"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "email_send_audits" not in inspector.get_table_names():
        op.create_table(
            "email_send_audits",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "magic_link_id",
                sa.Uuid(),
                sa.ForeignKey("magic_links.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column("source_app", sa.String(64), nullable=False),
            sa.Column("message_kind", sa.String(32), nullable=False),
            sa.Column("trigger_kind", sa.String(32), nullable=False),
            sa.Column("provenance", sa.String(40), nullable=False),
            sa.Column("org_id", sa.String(64), nullable=True),
            sa.Column("upstream_audit_id", sa.Uuid(), nullable=True),
            sa.Column("state", sa.String(16), nullable=False),
            sa.Column("provider_message_id", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("attempted_at", sa.DateTime(), nullable=True),
            sa.Column("accepted_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "state IN ('pending','sending','accepted','rejected','unknown','not_issued')",
                name="ck_email_send_audit_state",
            ),
            sa.CheckConstraint(
                "state != 'accepted' OR (provider_message_id IS NOT NULL AND length(trim(provider_message_id)) > 0 AND accepted_at IS NOT NULL)",
                name="ck_email_send_audit_receipt",
            ),
        )
        op.create_index(
            "ix_email_send_audit_source_created", "email_send_audits", ["source_app", "created_at"]
        )
        op.create_index("ix_email_send_audit_upstream", "email_send_audits", ["upstream_audit_id"])
        op.create_index(
            "ix_email_send_audit_provider", "email_send_audits", ["provider_message_id"]
        )
    if "payment_mail_dispatches" in sa.inspect(bind).get_table_names():
        dispatch_columns = {
            column["name"] for column in sa.inspect(bind).get_columns("payment_mail_dispatches")
        }
        if "map_audit_id" not in dispatch_columns:
            op.add_column(
                "payment_mail_dispatches", sa.Column("map_audit_id", sa.String(36), nullable=True)
            )
    columns = {column["name"] for column in sa.inspect(bind).get_columns("email_events")}
    for name, kind in [
        ("mail_audit_id", sa.String(36)),
        ("map_audit_id", sa.String(36)),
        ("message_kind", sa.String(32)),
        ("trigger_kind", sa.String(32)),
        ("command_id", sa.String(36)),
    ]:
        if name not in columns:
            op.add_column("email_events", sa.Column(name, kind, nullable=True))
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("email_events")}
    if "ix_email_events_mail_audit" not in indexes:
        op.create_index("ix_email_events_mail_audit", "email_events", ["mail_audit_id"])


def downgrade():
    # Evidence is retained on source rollback; no irreversible history cleanup.
    pass
