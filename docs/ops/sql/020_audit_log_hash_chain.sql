-- 020_audit_log_hash_chain — owner-applied DDL for Janua (PostgreSQL), for the
-- staging database (janua_staging) and the production database (janua).
--
-- WHY THIS FILE EXISTS. Neither staging nor production runs migrations:
-- promote-to-prod only moves image digests (RFC 0001, pattern B,
-- docs/runbooks/ALEMBIC_CONVERGENCE.md), and apps/api/docker-entrypoint.sh
-- applies alembic only when JANUA_APPLY_MIGRATIONS=true, which no overlay sets.
-- DDL is applied BY HAND in each database, BEFORE any image that maps these
-- columns runs there. The production ledger
-- apps/api/alembic/PROD_ALEMBIC_STATE.json is then refreshed in a separate,
-- reviewed PR (staging has no ledger). The five DDL statements below are,
-- character for character, UPGRADE_STATEMENTS in
-- apps/api/alembic/versions/020_audit_log_hash_chain.py (enforced by
-- apps/api/tests/unit/test_audit_log_hash_chain_migration.py, which also applies
-- BOTH to scratch databases and compares the catalogs).
--
-- HOW TO RUN, as the postgres superuser, in the pod that hosts each database
-- (production: the data/postgres pod), staging first:
--   psql -U postgres -d janua_staging -v ON_ERROR_STOP=1 -f 020_audit_log_hash_chain.sql
--   psql -U postgres -d janua -v ON_ERROR_STOP=1 -f 020_audit_log_hash_chain.sql
-- (or piped on stdin). One transaction per database. Idempotent: re-running it
-- after success changes nothing and still exits 0.
--
-- THE GUARD. Each database records its own revision in its own alembic_version
-- table, and this file moves that row from 019 to 020 in the database it runs
-- in. It refuses, and rolls back everything (nothing changes), unless
-- alembic_version holds exactly one row reading 019_email_first_party_engagement
-- or 020_audit_log_hash_chain. A refusal means that database is at another
-- revision (or has no alembic_version table): read its state first, and do not
-- edit the guard.
--   SELECT version_num FROM alembic_version
--   * Older than 019: that database also lacks later revisions. Bring it to 019
--     first with docs/ops/sql/018_email_events.sql and
--     019_email_first_party_engagement.sql, in order (each has its own guard),
--     then run this file again. Older than 017: stop and escalate.
--   * No alembic_version table (a database built from the models): run the
--     five DDL statements below by themselves, outside this file. They are
--     idempotent, and there is no version row to move.
--   * Newer than 020: there is nothing to apply.
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
--   * moves this database's alembic_version 019 -> 020.

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
