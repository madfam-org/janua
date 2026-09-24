-- 018_email_events — owner-applied production DDL for Janua (PostgreSQL).
--
-- WHY THIS FILE EXISTS. promote-to-prod does NOT run migrations (RFC 0001,
-- pattern B; docs/runbooks/ALEMBIC_CONVERGENCE.md). Production DDL is applied
-- BY HAND and the ledger apps/api/alembic/PROD_ALEMBIC_STATE.json is then
-- refreshed in a separate, reviewed PR. This file is object-for-object the
-- same as apps/api/alembic/versions/018_email_events.py (enforced by
-- apps/api/tests/unit/test_email_events_migration.py, which applies BOTH to
-- scratch databases and compares the catalogs).
--
-- HOW TO RUN (same shape as 017, 2026-09-23): in the data/postgres pod,
--   psql -U postgres -d janua -v ON_ERROR_STOP=1 -f 018_email_events.sql
-- One transaction. Idempotent: re-running it after success changes nothing
-- and still exits 0. It refuses (and rolls back everything) unless
-- alembic_version holds exactly one row reading 017_payment_mail_dispatch or
-- 018_email_events.
--
-- WHAT IT DOES: creates one new table + 2 indexes, grants the app role `janua`
-- SELECT/INSERT on it (append-only: no UPDATE, no DELETE) and USAGE on its
-- sequence, and moves alembic_version 017 -> 018. No existing table changes.
-- Objects are owned by `enclii`, like organizations/oauth_clients/alembic_version.

\set ON_ERROR_STOP on

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL ROLE enclii;

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
  IF v NOT IN ('017_payment_mail_dispatch', '018_email_events') THEN
    RAISE EXCEPTION 'expected alembic_version 017_payment_mail_dispatch (or 018_email_events), found %', v;
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS email_events (
  id BIGSERIAL NOT NULL,
  provider VARCHAR(16) DEFAULT 'resend' NOT NULL,
  cuenta VARCHAR(32) NOT NULL,
  svix_id VARCHAR(255) NOT NULL,
  email_id VARCHAR(255) NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  occurred_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  source_app VARCHAR(64),
  org_id VARCHAR(64),
  bounce_type VARCHAR(64),
  bounce_subtype VARCHAR(64),
  click_link VARCHAR(2048),
  received_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  CONSTRAINT pk_email_events PRIMARY KEY (id),
  CONSTRAINT uq_email_events_svix_id UNIQUE (svix_id)
);

CREATE INDEX IF NOT EXISTS ix_email_events_email_id ON email_events (email_id);
CREATE INDEX IF NOT EXISTS ix_email_events_source_app_id ON email_events (source_app, id);

GRANT SELECT, INSERT ON email_events TO janua;
GRANT USAGE, SELECT ON SEQUENCE email_events_id_seq TO janua;

UPDATE alembic_version
   SET version_num = '018_email_events'
 WHERE version_num = '017_payment_mail_dispatch';

DO $$
BEGIN
  IF (SELECT count(*) FROM alembic_version WHERE version_num = '018_email_events') <> 1 THEN
    RAISE EXCEPTION 'alembic_version did not land on 018_email_events';
  END IF;
END
$$;

COMMIT;

-- Post-commit verification (read-only; paste the output into the ledger PR):
--   SELECT version_num FROM alembic_version;                                   -- 018_email_events
--   SELECT tableowner FROM pg_tables WHERE tablename = 'email_events';         -- enclii
--   SELECT indexname FROM pg_indexes WHERE tablename = 'email_events' ORDER BY 1;
--     -- ix_email_events_email_id, ix_email_events_source_app_id, pk_email_events, uq_email_events_svix_id
--   SELECT has_table_privilege('janua', 'email_events', 'INSERT'),
--          has_table_privilege('janua', 'email_events', 'SELECT'),
--          has_table_privilege('janua', 'email_events', 'UPDATE'),              -- false
--          has_table_privilege('janua', 'email_events', 'DELETE'),              -- false
--          has_sequence_privilege('janua', 'email_events_id_seq', 'USAGE');
--   SELECT count(*) FROM email_events;                                         -- 0
