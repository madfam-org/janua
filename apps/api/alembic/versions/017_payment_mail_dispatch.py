"""Add bounded, tenant-bound payment-notice acceptance receipts.

No existing mail endpoint changes and no messages are backfilled. Apply before
using the new scoped route. A populated ledger cannot be downgraded: its receipt
and provider-window evidence must survive application rollback.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "017_payment_mail_dispatch"
down_revision = "016_org_member_app_roles"
branch_labels = None
depends_on = None
TABLE = "payment_mail_dispatches"

GUARD_SQL = """
CREATE OR REPLACE FUNCTION guard_payment_mail_dispatch() RETURNS trigger AS $$
BEGIN
  IF TG_OP IN ('DELETE', 'TRUNCATE') THEN
    RAISE EXCEPTION 'payment mail evidence cannot be erased';
  END IF;
  IF TG_OP = 'INSERT' THEN
    PERFORM 1 FROM oauth_clients WHERE id = NEW.client_id
      AND organization_id = NEW.organization_id FOR SHARE;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'payment mail client organization mismatch';
    END IF;
    IF NEW.state != 'sending' OR NEW.attempts != 1 OR NEW.attempt_id IS NULL
       OR NEW.first_attempt_at IS NULL OR NEW.lease_until IS NULL
       OR NEW.provider_message_id IS NOT NULL OR NEW.accepted_at IS NOT NULL THEN
      RAISE EXCEPTION 'payment mail evidence must start with a first sending claim';
    END IF;
    RETURN NEW;
  END IF;
  IF ROW(NEW.id, NEW.organization_id, NEW.client_id, NEW.command_id,
         NEW.request_hash, NEW.envelope_hash, NEW.binding_hash,
         NEW.credential_fingerprint, NEW.created_at)
     IS DISTINCT FROM
     ROW(OLD.id, OLD.organization_id, OLD.client_id, OLD.command_id,
         OLD.request_hash, OLD.envelope_hash, OLD.binding_hash,
         OLD.credential_fingerprint, OLD.created_at) THEN
    RAISE EXCEPTION 'payment mail command identity is immutable';
  END IF;
  IF OLD.state IN ('accepted', 'review') AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'payment mail final evidence is immutable';
  END IF;
  IF OLD.first_attempt_at IS NOT NULL
     AND NEW.first_attempt_at IS DISTINCT FROM OLD.first_attempt_at THEN
    RAISE EXCEPTION 'payment mail first attempt is immutable';
  END IF;
  IF NEW.attempts < OLD.attempts OR NEW.attempts > OLD.attempts + 1 THEN
    RAISE EXCEPTION 'payment mail attempt count must advance one at a time';
  END IF;
  IF NEW.attempts > OLD.attempts AND
     (NEW.state != 'sending' OR NEW.attempt_id IS NOT DISTINCT FROM OLD.attempt_id) THEN
    RAISE EXCEPTION 'payment mail new attempt requires a new sending lease';
  END IF;
  IF NEW.attempts = OLD.attempts AND NEW.attempt_id IS DISTINCT FROM OLD.attempt_id THEN
    RAISE EXCEPTION 'payment mail attempt identity cannot change without a claim';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS payment_mail_dispatch_guard ON payment_mail_dispatches;
CREATE TRIGGER payment_mail_dispatch_guard BEFORE INSERT OR UPDATE OR DELETE
  ON payment_mail_dispatches FOR EACH ROW EXECUTE FUNCTION guard_payment_mail_dispatch();
DROP TRIGGER IF EXISTS payment_mail_dispatch_no_truncate ON payment_mail_dispatches;
CREATE TRIGGER payment_mail_dispatch_no_truncate BEFORE TRUNCATE
  ON payment_mail_dispatches FOR EACH STATEMENT EXECUTE FUNCTION guard_payment_mail_dispatch();
"""


def upgrade():
    bind = op.get_bind()
    if TABLE not in sa.inspect(bind).get_table_names():
        op.create_table(
            TABLE,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "organization_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "client_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("oauth_clients.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
            *[
                sa.Column(name, sa.String(64), nullable=False)
                for name in (
                    "request_hash",
                    "envelope_hash",
                    "binding_hash",
                    "credential_fingerprint",
                )
            ],
            sa.Column("state", sa.String(16), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("attempt_id", postgresql.UUID(as_uuid=True)),
            *[
                sa.Column(name, sa.DateTime())
                for name in ("first_attempt_at", "lease_until", "next_attempt_at", "accepted_at")
            ],
            sa.Column("provider_message_id", sa.String(255)),
            sa.Column("issue", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "organization_id", "client_id", "command_id", name="uq_payment_mail_command"
            ),
            sa.CheckConstraint("attempts >= 0", name="ck_payment_mail_attempts"),
            sa.CheckConstraint(
                "state IN ('pending', 'sending', 'accepted', 'review')",
                name="ck_payment_mail_state",
            ),
            sa.CheckConstraint(
                "state != 'accepted' OR (provider_message_id IS NOT NULL "
                "AND length(trim(provider_message_id)) > 0 AND accepted_at IS NOT NULL)",
                name="ck_payment_mail_receipt",
            ),
        )
    if bind.dialect.name == "postgresql":
        # asyncpg accepts a single prepared statement at a time.
        function, triggers = GUARD_SQL.split("DROP TRIGGER", 1)
        op.execute(function)
        for statement in ("DROP TRIGGER" + triggers).split(";"):
            if statement.strip():
                op.execute(statement)


def downgrade():
    bind = op.get_bind()
    if TABLE not in sa.inspect(bind).get_table_names():
        return
    if bind.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first():
        raise RuntimeError("Cannot discard payment-mail evidence; roll back application only")
    op.drop_table(TABLE)
    if bind.dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS guard_payment_mail_dispatch()")
