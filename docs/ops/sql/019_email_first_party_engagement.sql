-- 019_email_first_party_engagement — owner-applied production DDL for Janua (PostgreSQL).
--
-- WHY THIS FILE EXISTS. promote-to-prod does NOT run migrations (RFC 0001,
-- pattern B; docs/runbooks/ALEMBIC_CONVERGENCE.md). Production DDL is applied
-- BY HAND and the ledger apps/api/alembic/PROD_ALEMBIC_STATE.json is then
-- refreshed in a separate, reviewed PR. This file is object-for-object the
-- same as apps/api/alembic/versions/019_email_first_party_engagement.py
-- (enforced by apps/api/tests/unit/test_email_engagement_migration.py, which
-- applies BOTH to scratch databases and compares the catalogs).
--
-- HOW TO RUN (same shape as 018, 2026-09-23): in the data/postgres pod,
--   psql -U postgres -d janua -v ON_ERROR_STOP=1 -f 019_email_first_party_engagement.sql
-- One transaction. Idempotent: re-running it after success changes nothing
-- and still exits 0. It refuses (and rolls back everything) unless
-- alembic_version holds exactly one row reading 018_email_events or
-- 019_email_first_party_engagement.
--
-- WHAT IT DOES:
--   * email_events gains `source` (NOT NULL DEFAULT 'webhook': every existing
--     row reads as a webhook row; a constant default is a catalog-only change
--     on PostgreSQL 11+, no table rewrite) and `possible_prefetch` (nullable).
--     Its grants do not change: the app role stays SELECT/INSERT (append-only).
--   * creates email_tracking_links + 1 index, owned by `enclii`, and grants the
--     app role `janua` SELECT/INSERT/UPDATE on it (UPDATE binds the Resend
--     email_id to a token row right after the send; no DELETE).
--   * moves alembic_version 018 -> 019.

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
  IF v NOT IN ('018_email_events', '019_email_first_party_engagement') THEN
    RAISE EXCEPTION 'expected alembic_version 018_email_events (or 019_email_first_party_engagement), found %', v;
  END IF;
END
$$;

ALTER TABLE email_events ADD COLUMN IF NOT EXISTS source VARCHAR(16) DEFAULT 'webhook' NOT NULL;
ALTER TABLE email_events ADD COLUMN IF NOT EXISTS possible_prefetch BOOLEAN;

CREATE TABLE IF NOT EXISTS email_tracking_links (
  token_hash VARCHAR(64) NOT NULL,
  cuenta VARCHAR(32) NOT NULL,
  source_app VARCHAR(64),
  org_id VARCHAR(64),
  email_id VARCHAR(255),
  links TEXT NOT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  CONSTRAINT pk_email_tracking_links PRIMARY KEY (token_hash)
);

CREATE INDEX IF NOT EXISTS ix_email_tracking_links_email_id ON email_tracking_links (email_id);

GRANT SELECT, INSERT, UPDATE ON email_tracking_links TO janua;

UPDATE alembic_version
   SET version_num = '019_email_first_party_engagement'
 WHERE version_num = '018_email_events';

DO $$
BEGIN
  IF (SELECT count(*) FROM alembic_version WHERE version_num = '019_email_first_party_engagement') <> 1 THEN
    RAISE EXCEPTION 'alembic_version did not land on 019_email_first_party_engagement';
  END IF;
END
$$;

COMMIT;

-- Post-commit verification (read-only; paste the output into the ledger PR):
--   SELECT version_num FROM alembic_version;                                   -- 019_email_first_party_engagement
--   SELECT column_name, data_type, is_nullable, column_default
--     FROM information_schema.columns
--    WHERE table_name = 'email_events' AND column_name IN ('source', 'possible_prefetch')
--    ORDER BY 1;
--     -- possible_prefetch | boolean | YES |
--     -- source | character varying | NO | 'webhook'::character varying
--   SELECT tableowner FROM pg_tables WHERE tablename = 'email_tracking_links'; -- enclii
--   SELECT indexname FROM pg_indexes WHERE tablename = 'email_tracking_links' ORDER BY 1;
--     -- ix_email_tracking_links_email_id, pk_email_tracking_links
--   SELECT has_table_privilege('janua', 'email_tracking_links', 'SELECT'),
--          has_table_privilege('janua', 'email_tracking_links', 'INSERT'),
--          has_table_privilege('janua', 'email_tracking_links', 'UPDATE'),
--          has_table_privilege('janua', 'email_tracking_links', 'DELETE');    -- t, t, t, f
--   SELECT has_table_privilege('janua', 'email_events', 'UPDATE');            -- false (unchanged)
--   SELECT source, count(*) FROM email_events GROUP BY 1;                      -- only 'webhook'
--   SELECT count(*) FROM email_tracking_links;                                 -- 0
