-- 023_device_clients — owner-applied DDL for Janua (PostgreSQL).
--
-- WHY THIS FILE EXISTS. promote-to-prod does NOT run migrations (RFC 0001,
-- pattern B; docs/runbooks/ALEMBIC_CONVERGENCE.md), and the staging overlay
-- sets JANUA_APPLY_MIGRATIONS=false. DDL is applied BY HAND, through Enclii's
-- migration adapter where one exists (record the gap where it does not), and
-- the ledger apps/api/alembic/PROD_ALEMBIC_STATE.json is then refreshed in a
-- separate, reviewed PR after reading the database back. This file is
-- object-for-object the same as
-- apps/api/alembic/versions/023_device_clients.py (enforced by
-- apps/api/tests/unit/test_device_clients_postgres.py, which applies BOTH to
-- scratch databases and compares the catalogs).
--
-- ORDER DOES NOT MATTER FOR AVAILABILITY. These tables are read only by the
-- device enrolment routes and, at the token endpoint, only for a device client
-- (client_id prefix jnd_), which cannot exist before these tables do. An image
-- with revision 023 on a database without them serves every other client
-- exactly as before; the enrolment routes fail with a server error and the
-- feature is simply off. These tables on a database whose image predates 023
-- are never read.
--
-- HOW TO RUN (same shape as 022): in the data/postgres pod,
--   psql -U postgres -d janua -v ON_ERROR_STOP=1 -f 023_device_clients.sql
-- One transaction. Idempotent: re-running it after success changes nothing and
-- still exits 0. It refuses (and rolls back everything) unless alembic_version
-- holds exactly one row reading 022_user_primary_organization or
-- 023_device_clients.
--
-- WHAT IT DOES:
--   * creates device_clients (owned by `enclii`, empty): the identity record of
--     each shared device, one per device OAuth client, plus
--     ix_device_clients_organization_id;
--   * creates device_enrolments (owned by `enclii`, empty): requests waiting
--     for an organization administrator's approval, plus
--     ix_device_enrolments_organization_id_status;
--     The foreign keys take short locks on oauth_clients, organizations and
--     users; new, empty tables mean nothing to validate. lock_timeout bounds
--     the wait; on timeout everything rolls back and it can be re-run.
--   * grants the app role `janua` SELECT, INSERT, UPDATE on both (no DELETE:
--     a device is disabled, never deleted, and the cascades run as the owner).
--   * no existing table, column, index or grant changes.
--   * moves alembic_version 022 -> 023.

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
  IF n <> 1 OR v NOT IN ('022_user_primary_organization', '023_device_clients') THEN
    RAISE EXCEPTION 'expected alembic_version 022_user_primary_organization (or 023_device_clients), found % row(s), %', n, v;
  END IF;
END
$$;

-- Constraint names are explicit and match what alembic emits under the
-- metadata naming convention (app/core/database.py), so the two paths agree.
CREATE TABLE IF NOT EXISTS device_clients (
  id UUID NOT NULL,
  oauth_client_id UUID NOT NULL,
  organization_id UUID NOT NULL,
  template VARCHAR(64) NOT NULL,
  label VARCHAR(100) NOT NULL,
  status VARCHAR(16) NOT NULL,
  approved_by UUID,
  approved_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  disabled_by UUID,
  disabled_at TIMESTAMP WITHOUT TIME ZONE,
  disabled_reason VARCHAR(300),
  last_token_at TIMESTAMP WITHOUT TIME ZONE,
  recent_boot_ids VARCHAR(400),
  boot_alternations INTEGER DEFAULT 0 NOT NULL,
  clone_suspected_at TIMESTAMP WITHOUT TIME ZONE,
  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  CONSTRAINT pk_device_clients PRIMARY KEY (id),
  CONSTRAINT uq_device_clients_oauth_client_id UNIQUE (oauth_client_id),
  CONSTRAINT fk_device_clients_oauth_client_id_oauth_clients
    FOREIGN KEY (oauth_client_id) REFERENCES oauth_clients (id) ON DELETE CASCADE,
  CONSTRAINT fk_device_clients_organization_id_organizations
    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
  CONSTRAINT fk_device_clients_approved_by_users
    FOREIGN KEY (approved_by) REFERENCES users (id) ON DELETE SET NULL,
  CONSTRAINT fk_device_clients_disabled_by_users
    FOREIGN KEY (disabled_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_device_clients_organization_id
  ON device_clients (organization_id);

CREATE TABLE IF NOT EXISTS device_enrolments (
  id UUID NOT NULL,
  organization_id UUID NOT NULL,
  template VARCHAR(64) NOT NULL,
  label VARCHAR(100) NOT NULL,
  user_code VARCHAR(9) NOT NULL,
  secret_hash VARCHAR(255),
  status VARCHAR(16) NOT NULL,
  replaces_device_id UUID,
  requested_ip VARCHAR(64),
  requested_user_agent VARCHAR(255),
  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  approved_by UUID,
  approved_at TIMESTAMP WITHOUT TIME ZONE,
  device_id UUID,
  CONSTRAINT pk_device_enrolments PRIMARY KEY (id),
  CONSTRAINT uq_device_enrolments_user_code UNIQUE (user_code),
  CONSTRAINT fk_device_enrolments_organization_id_organizations
    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
  CONSTRAINT fk_device_enrolments_replaces_device_id_device_clients
    FOREIGN KEY (replaces_device_id) REFERENCES device_clients (id) ON DELETE SET NULL,
  CONSTRAINT fk_device_enrolments_approved_by_users
    FOREIGN KEY (approved_by) REFERENCES users (id) ON DELETE SET NULL,
  CONSTRAINT fk_device_enrolments_device_id_device_clients
    FOREIGN KEY (device_id) REFERENCES device_clients (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_device_enrolments_organization_id_status
  ON device_enrolments (organization_id, status);

GRANT SELECT, INSERT, UPDATE ON device_clients TO janua;
GRANT SELECT, INSERT, UPDATE ON device_enrolments TO janua;

UPDATE alembic_version
   SET version_num = '023_device_clients'
 WHERE version_num = '022_user_primary_organization';

DO $$
BEGIN
  IF (SELECT count(*) FROM alembic_version WHERE version_num = '023_device_clients') <> 1 THEN
    RAISE EXCEPTION 'alembic_version did not land on 023_device_clients';
  END IF;
END
$$;

COMMIT;

-- Post-commit verification (read-only; paste the output into the ledger PR):
--   SELECT version_num FROM alembic_version;            -- 023_device_clients
--   SELECT tablename, tableowner FROM pg_tables
--    WHERE tablename IN ('device_clients', 'device_enrolments') ORDER BY 1;  -- both enclii
--   SELECT table_name, column_name, data_type, is_nullable
--     FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name IN ('device_clients', 'device_enrolments')
--    ORDER BY table_name, column_name;
--   SELECT conrelid::regclass, conname, pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conrelid IN ('public.device_clients'::regclass, 'public.device_enrolments'::regclass)
--    ORDER BY 1, 2;
--   SELECT tablename, indexname FROM pg_indexes
--    WHERE tablename IN ('device_clients', 'device_enrolments') ORDER BY 1, 2;
--   SELECT has_table_privilege('janua', 'device_clients', 'DELETE'),
--          has_table_privilege('janua', 'device_enrolments', 'DELETE');  -- f, f
--   SELECT (SELECT count(*) FROM device_clients), (SELECT count(*) FROM device_enrolments);  -- 0, 0
--
-- Only after reading the database back: a reviewed PR moving
-- PROD_ALEMBIC_STATE.json to 023_device_clients, with that output.
