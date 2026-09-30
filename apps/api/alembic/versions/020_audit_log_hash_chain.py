"""Hash-chain columns on audit_logs for app/services/audit_logger.py.

Additive only. `audit_logs` gains four nullable columns and one index:

- `event_type`     VARCHAR(100): the audit event name (`auth.signin`, ...). The
                   service also writes it to `action`, which stays NOT NULL.
- `tenant_id`      VARCHAR(255): the chain key. Callers pass organization ids,
                   tenant ids and labels such as `default`, so it is text, not
                   a UUID.
- `current_hash`   VARCHAR(64): SHA-256 hex of the entry.
- `previous_hash`  VARCHAR(64): the `current_hash` of the tenant's previous entry.
- `ix_audit_logs_tenant_chain` on (tenant_id, created_at, id): the lookup of a
  tenant's latest entry and the ordered walk that verifies the chain.

Every column is nullable and has no default, so existing rows and the other
code that writes `audit_logs` (with `action` only) are unaffected, and adding
them is a catalog-only change on PostgreSQL.

Re-entrant by contract, because production applies DDL by hand: every statement
is `IF NOT EXISTS` / `IF EXISTS`. The owner-ready SQL for production is
docs/ops/sql/020_audit_log_hash_chain.sql and runs exactly the statements in
UPGRADE_STATEMENTS (tests/unit/test_audit_log_hash_chain_migration.py compares
the text and the resulting catalogs).

Downgrade drops the index and the four columns, and with them the chain data of
rows written by the audit logger. Those rows keep `action` and the rest.
"""

from alembic import op

revision = "020_audit_log_hash_chain"
down_revision = "019_email_first_party_engagement"
branch_labels = None
depends_on = None

UPGRADE_STATEMENTS = (
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS event_type VARCHAR(100)",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255)",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS current_hash VARCHAR(64)",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS previous_hash VARCHAR(64)",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_tenant_chain "
    "ON audit_logs (tenant_id, created_at, id)",
)

DOWNGRADE_STATEMENTS = (
    "DROP INDEX IF EXISTS ix_audit_logs_tenant_chain",
    "ALTER TABLE audit_logs DROP COLUMN IF EXISTS previous_hash",
    "ALTER TABLE audit_logs DROP COLUMN IF EXISTS current_hash",
    "ALTER TABLE audit_logs DROP COLUMN IF EXISTS tenant_id",
    "ALTER TABLE audit_logs DROP COLUMN IF EXISTS event_type",
)


def upgrade():
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade():
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
