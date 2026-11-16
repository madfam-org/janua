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
-- ORDER DOES NOT MATTER FOR AVAILABILITY. Nothing on the login path reads this
-- table except the claims resolver, and it reads it in a guarded SAVEPOINT that
-- answers "no primary" on any failure, a missing table included. An image with
-- revision 022 on a database without this table mints exactly today's tokens;
-- this table on a database whose image predates 022 is never read. Until both
-- are present, the operator endpoints (/api/v1/internal/primary-organization)
-- fail with a server error (503) and the feature is simply off.
--
-- HOW TO RUN (same shape as 019): in the data/postgres pod,
--   psql -U postgres -d janua -v ON_ERROR_STOP=1 -f 022_user_primary_organization.sql
-- One transaction. Idempotent: re-running it after success changes nothing and
-- still exits 0. It refuses (and rolls back everything) unless alembic_version
-- holds exactly one row reading 021_map_email_traceability or
-- 022_user_primary_organization.
--
-- WHAT IT DOES:
--   * creates user_primary_organizations (owned by `enclii`, empty):
--       user_id         UUID PK -> users(id)          ON DELETE CASCADE
--       organization_id UUID NULL -> organizations(id) ON DELETE CASCADE
--       set_by          VARCHAR(255) NOT NULL
--       set_at          TIMESTAMP NOT NULL
--     plus ix_user_primary_organizations_organization_id.
--     The foreign keys take short locks on users and organizations; a new,
--     empty table means nothing to validate. lock_timeout bounds the wait; on
--     timeout everything rolls back and it can be re-run.
--   * grants the app role `janua` SELECT, INSERT, UPDATE (no DELETE: clearing
--     is an UPDATE to NULL, and the cascades run as the table owner).
--   * no existing table, column, index or grant changes.
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

-- Constraint names are explicit and match what alembic emits under the
-- metadata naming convention (app/core/database.py), so the two paths agree.
CREATE TABLE IF NOT EXISTS user_primary_organizations (
  user_id UUID NOT NULL,
  organization_id UUID,
  set_by VARCHAR(255) NOT NULL,
  set_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  CONSTRAINT pk_user_primary_organizations PRIMARY KEY (user_id),
  CONSTRAINT fk_user_primary_organizations_user_id_users
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_user_primary_organizations_organization_id_organizations
    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_user_primary_organizations_organization_id
  ON user_primary_organizations (organization_id);

GRANT SELECT, INSERT, UPDATE ON user_primary_organizations TO janua;

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
--   SELECT version_num FROM alembic_version;            -- 022_user_primary_organization
--   SELECT tableowner FROM pg_tables WHERE tablename = 'user_primary_organizations';  -- enclii
--   SELECT column_name, data_type, is_nullable
--     FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name = 'user_primary_organizations'
--    ORDER BY column_name;
--     -- organization_id | uuid | YES
--     -- set_at | timestamp without time zone | NO
--     -- set_by | character varying | NO
--     -- user_id | uuid | NO
--   SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conrelid = 'public.user_primary_organizations'::regclass ORDER BY conname;
--     -- fk_user_primary_organizations_organization_id_organizations | FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
--     -- fk_user_primary_organizations_user_id_users | FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
--     -- pk_user_primary_organizations | PRIMARY KEY (user_id)
--   SELECT indexname FROM pg_indexes WHERE tablename = 'user_primary_organizations' ORDER BY 1;
--     -- ix_user_primary_organizations_organization_id, pk_user_primary_organizations
--   SELECT has_table_privilege('janua', 'user_primary_organizations', 'SELECT'),
--          has_table_privilege('janua', 'user_primary_organizations', 'INSERT'),
--          has_table_privilege('janua', 'user_primary_organizations', 'UPDATE'),
--          has_table_privilege('janua', 'user_primary_organizations', 'DELETE');  -- t, t, t, f
--   SELECT count(*) FROM user_primary_organizations;    -- 0
--
-- scripts/alembic_converge.py --check only knows revisions 012-016, so it does
-- not verify this one: the queries above ARE the readback for 022 (as for
-- 017-021). Only after reading the database back: a reviewed PR moving
-- PROD_ALEMBIC_STATE.json to 022_user_primary_organization, with that output.
