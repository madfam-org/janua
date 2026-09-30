-- 020_audit_log_hash_chain — owner-applied production DDL for Janua (PostgreSQL).
--
-- WHY THIS FILE EXISTS. promote-to-prod does NOT run migrations (RFC 0001,
-- pattern B; docs/runbooks/ALEMBIC_CONVERGENCE.md). Production DDL is applied
-- BY HAND and the ledger apps/api/alembic/PROD_ALEMBIC_STATE.json is then
-- refreshed in a separate, reviewed PR. The five DDL statements below are,
-- character for character, UPGRADE_STATEMENTS in
-- apps/api/alembic/versions/020_audit_log_hash_chain.py (enforced by
-- apps/api/tests/unit/test_audit_log_hash_chain_migration.py, which also applies
-- BOTH to scratch databases and compares the catalogs).
--
-- HOW TO RUN: in the data/postgres pod, as the postgres superuser,
--   psql -U postgres -d janua -v ON_ERROR_STOP=1 -f 020_audit_log_hash_chain.sql
-- (or piped on stdin). One transaction. Idempotent: re-running it after success
-- changes nothing and still exits 0. It refuses (and rolls back everything)
-- unless alembic_version holds exactly one row reading
-- 019_email_first_party_engagement or 020_audit_log_hash_chain.
--
-- No SET ROLE: nothing here creates a table, so no new object needs an owner.
-- The superuser can alter audit_logs whichever role owns it, and the new index
-- belongs to the table's owner automatically. Column privileges follow the
-- table-level grants, so the app role's existing SELECT/INSERT on audit_logs
-- covers the new columns.
--
-- WHAT IT DOES:
--   * audit_logs gains event_type, tenant_id, current_hash and previous_hash,
--     all nullable with no default: a catalog-only change, no table rewrite,
--     existing rows read NULL.
--   * creates ix_audit_logs_tenant_chain (tenant_id, created_at, id). This is a
--     plain CREATE INDEX, which blocks writes to audit_logs while it builds;
--     check the table's row count first (the drift check prints it).
--   * moves alembic_version 019 -> 020.

\set ON_ERROR_STOP on

BEGIN;

SET LOCAL lock_timeout = '5s';

DO $$
DECLARE
  n integer;
  v text;
BEGIN
  SELECT count(*) INTO n FROM alembic_version;
  IF n <> 1 THEN
    RAISE EXCEPTION 'alembic_version must hold exactly 1 row, found %', n;
  END IF;
  SELECT version_num INTO v FROM alembic_version;
  IF v NOT IN ('019_email_first_party_engagement', '020_audit_log_hash_chain') THEN
    RAISE EXCEPTION 'expected alembic_version 019_email_first_party_engagement (or 020_audit_log_hash_chain), found %', v;
  END IF;
END
$$;

ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS event_type VARCHAR(100);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(255);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS current_hash VARCHAR(64);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS previous_hash VARCHAR(64);
CREATE INDEX IF NOT EXISTS ix_audit_logs_tenant_chain ON audit_logs (tenant_id, created_at, id);

UPDATE alembic_version
   SET version_num = '020_audit_log_hash_chain'
 WHERE version_num = '019_email_first_party_engagement';

DO $$
BEGIN
  IF (SELECT count(*) FROM alembic_version WHERE version_num = '020_audit_log_hash_chain') <> 1 THEN
    RAISE EXCEPTION 'alembic_version did not land on 020_audit_log_hash_chain';
  END IF;
END
$$;

COMMIT;

-- Post-commit verification (read-only; paste the output into the ledger PR):
--   SELECT version_num FROM alembic_version;                  -- 020_audit_log_hash_chain
--   SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
--     FROM information_schema.columns
--    WHERE table_name = 'audit_logs'
--      AND column_name IN ('event_type', 'tenant_id', 'current_hash', 'previous_hash')
--    ORDER BY 1;
--     -- current_hash  | character varying |  64 | YES |
--     -- event_type    | character varying | 100 | YES |
--     -- previous_hash | character varying |  64 | YES |
--     -- tenant_id     | character varying | 255 | YES |
--   SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_audit_logs_tenant_chain';
--     -- CREATE INDEX ix_audit_logs_tenant_chain ON public.audit_logs USING btree (tenant_id, created_at, id)
--   SELECT count(*) FROM audit_logs WHERE tenant_id IS NOT NULL;   -- 0 until the new image runs
