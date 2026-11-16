-- 022_user_primary_organization — owner-applied DDL for Janua (PostgreSQL).
--
-- WHY THIS FILE EXISTS. promote-to-prod does NOT run migrations (RFC 0001,
-- pattern B; docs/runbooks/ALEMBIC_CONVERGENCE.md), and the staging overlay
-- sets JANUA_APPLY_MIGRATIONS=false. DDL is applied BY HAND, through Enclii's
-- migration adapter where one exists (record the gap where it does not), and
-- the ledger apps/api/alembic/PROD_ALEMBIC_STATE.json is then refreshed in a
-- separate, reviewed PR after reading the database back. This file is
-- object-for-object the same as
-- apps/api/alembic/versions/022_user_primary_organization.py (enforced by
-- apps/api/tests/unit/test_user_primary_organization_postgres.py, which applies
-- BOTH to scratch databases and compares the catalogs).
--
-- ORDER. Apply this BEFORE any API image that carries revision 022 runs
-- against the database. The User model selects and inserts the new column, so
-- an image that meets a database without it fails every login loudly (the same
-- property 015, users.is_service_account, had). The column is inert for every
-- existing image: nothing older reads it.
--
-- HOW TO RUN (same shape as 019): in the data/postgres pod,
--   psql -U postgres -d janua -v ON_ERROR_STOP=1 -f 022_user_primary_organization.sql
-- One transaction. Idempotent: re-running it after success changes nothing and
-- still exits 0. It refuses (and rolls back everything) unless alembic_version
-- holds exactly one row reading 021_map_email_traceability or
-- 022_user_primary_organization, or if the app role `janua` would not be able
-- to read and write the new column.
--
-- WHAT IT DOES:
--   * users gains primary_organization_id (UUID, NULL, no default: a
--     catalog-only change, no table rewrite). Every existing row reads NULL,
--     which is today's behaviour exactly.
--   * adds fk_users_primary_organization_id -> organizations(id) ON DELETE SET
--     NULL. Validation reads users once; every value is NULL, so it rejects
--     nothing. lock_timeout bounds the wait for the locks on users and
--     organizations; on timeout everything rolls back and it can be re-run.
--   * no grant changes: the app role's existing table privileges on users
--     cover the new column (checked below, not assumed).
--   * moves alembic_version 021 -> 022.

\set ON_ERROR_STOP on

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL ROLE enclii;

DO $$
DECLARE
  n integer;
  v text;
BEGIN
  SELECT count(*), min(version_num) INTO n, v FROM alembic_version;
  IF n <> 1 OR v NOT IN ('021_map_email_traceability', '022_user_primary_organization') THEN
    RAISE EXCEPTION 'expected alembic_version 021_map_email_traceability (or 022_user_primary_organization), found % row(s), %', n, v;
  END IF;
END
$$;

ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_organization_id UUID;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conrelid = 'public.users'::regclass
       AND conname = 'fk_users_primary_organization_id'
  ) THEN
    ALTER TABLE users
      ADD CONSTRAINT fk_users_primary_organization_id
      FOREIGN KEY (primary_organization_id) REFERENCES organizations (id) ON DELETE SET NULL;
  END IF;
END
$$;

DO $$
BEGIN
  -- has_column_privilege with a LIST answers "any of"; check each one.
  IF NOT (has_column_privilege('janua', 'public.users', 'primary_organization_id', 'SELECT')
      AND has_column_privilege('janua', 'public.users', 'primary_organization_id', 'INSERT')
      AND has_column_privilege('janua', 'public.users', 'primary_organization_id', 'UPDATE')) THEN
    RAISE EXCEPTION 'app role janua cannot SELECT/INSERT/UPDATE users.primary_organization_id; refusing';
  END IF;
END
$$;

UPDATE alembic_version
   SET version_num = '022_user_primary_organization'
 WHERE version_num = '021_map_email_traceability';

DO $$
BEGIN
  IF (SELECT count(*) FROM alembic_version WHERE version_num = '022_user_primary_organization') <> 1 THEN
    RAISE EXCEPTION 'alembic_version did not land on 022_user_primary_organization';
  END IF;
END
$$;

COMMIT;

-- Post-commit verification (read-only; paste the output into the ledger PR):
--   SELECT version_num FROM alembic_version;                -- 022_user_primary_organization
--   SELECT data_type, is_nullable, column_default
--     FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name = 'users'
--      AND column_name = 'primary_organization_id';        -- uuid | YES | (null)
--   SELECT pg_get_constraintdef(oid), convalidated
--     FROM pg_constraint
--    WHERE conname = 'fk_users_primary_organization_id';
--     -- FOREIGN KEY (primary_organization_id) REFERENCES organizations(id) ON DELETE SET NULL | t
--   SELECT has_column_privilege('janua', 'public.users', 'primary_organization_id', 'SELECT'),
--          has_column_privilege('janua', 'public.users', 'primary_organization_id', 'INSERT'),
--          has_column_privilege('janua', 'public.users', 'primary_organization_id', 'UPDATE');
--     -- t, t, t
--   SELECT count(*) FROM users WHERE primary_organization_id IS NOT NULL;  -- 0
--
-- scripts/alembic_converge.py --check only knows revisions 012-016, so it does
-- not verify this one: the queries above ARE the readback for 022 (as for
-- 017-021). Only after reading the database back: a reviewed PR moving
-- PROD_ALEMBIC_STATE.json to 022_user_primary_organization, with that output.
