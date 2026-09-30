-- 020_white_label_branding_columns — owner-applied production DDL for Janua (PostgreSQL).
--
-- WHY THIS FILE EXISTS. promote-to-prod does NOT run migrations (RFC 0001,
-- pattern B; docs/runbooks/ALEMBIC_CONVERGENCE.md). Production DDL is applied
-- BY HAND and the ledger apps/api/alembic/PROD_ALEMBIC_STATE.json is then
-- refreshed in a separate, reviewed PR. This file is object-for-object the
-- same as apps/api/alembic/versions/020_white_label_branding_columns.py
-- (enforced by apps/api/tests/unit/test_white_label_branding_migration.py,
-- which applies BOTH to scratch databases and compares the catalogs).
--
-- ORDER. Apply this BEFORE promoting any api image that carries the
-- white-label fix: that image's model selects these columns, so without them
-- every /white-label/branding call fails with UndefinedColumn (still a 500,
-- as today, but now for a different reason). Nothing else reads this table.
--
-- HOW TO RUN (same shape as 019, 2026-09-25): in the data/postgres pod,
--   psql -U postgres -d janua -v ON_ERROR_STOP=1 -f 020_white_label_branding_columns.sql
-- One transaction. Idempotent: re-running it after success changes nothing
-- and still exits 0. It refuses (and rolls back everything) unless
-- alembic_version holds exactly one row reading 019_email_first_party_engagement
-- or 020_white_label_branding_columns, and unless white_label_configurations
-- exists and is owned by `enclii`.
--
-- WHAT IT DOES:
--   * white_label_configurations gains ten nullable columns with no default
--     (catalog-only: no table rewrite, no backfill; NULL means "not chosen").
--     No existing column, index, constraint or grant changes.
--   * moves alembic_version 019 -> 020.

\set ON_ERROR_STOP on

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL ROLE enclii;

DO $$
DECLARE
  n integer;
  v text;
  owner text;
BEGIN
  SELECT count(*) INTO n FROM alembic_version;
  IF n <> 1 THEN
    RAISE EXCEPTION 'alembic_version must hold exactly 1 row, found %', n;
  END IF;
  SELECT version_num INTO v FROM alembic_version;
  IF v NOT IN ('019_email_first_party_engagement', '020_white_label_branding_columns') THEN
    RAISE EXCEPTION 'expected alembic_version 019_email_first_party_engagement (or 020_white_label_branding_columns), found %', v;
  END IF;
  SELECT tableowner INTO owner FROM pg_tables
   WHERE schemaname = 'public' AND tablename = 'white_label_configurations';
  IF owner IS NULL THEN
    RAISE EXCEPTION 'table white_label_configurations does not exist';
  END IF;
  IF owner <> 'enclii' THEN
    RAISE EXCEPTION 'white_label_configurations is owned by %, expected enclii', owner;
  END IF;
END
$$;

ALTER TABLE white_label_configurations ADD COLUMN IF NOT EXISTS branding_level VARCHAR(20);
ALTER TABLE white_label_configurations ADD COLUMN IF NOT EXISTS theme_mode VARCHAR(10);
ALTER TABLE white_label_configurations ADD COLUMN IF NOT EXISTS logo_dark_url VARCHAR(500);
ALTER TABLE white_label_configurations ADD COLUMN IF NOT EXISTS website_url VARCHAR(500);
ALTER TABLE white_label_configurations ADD COLUMN IF NOT EXISTS accent_color VARCHAR(7);
ALTER TABLE white_label_configurations ADD COLUMN IF NOT EXISTS background_color VARCHAR(7);
ALTER TABLE white_label_configurations ADD COLUMN IF NOT EXISTS surface_color VARCHAR(7);
ALTER TABLE white_label_configurations ADD COLUMN IF NOT EXISTS text_color VARCHAR(7);
ALTER TABLE white_label_configurations ADD COLUMN IF NOT EXISTS font_family VARCHAR(255);
ALTER TABLE white_label_configurations ADD COLUMN IF NOT EXISTS border_radius VARCHAR(20);

UPDATE alembic_version
   SET version_num = '020_white_label_branding_columns'
 WHERE version_num = '019_email_first_party_engagement';

DO $$
BEGIN
  IF (SELECT count(*) FROM alembic_version WHERE version_num = '020_white_label_branding_columns') <> 1 THEN
    RAISE EXCEPTION 'alembic_version did not land on 020_white_label_branding_columns';
  END IF;
END
$$;

COMMIT;

-- Post-commit verification (read-only; paste the output into the ledger PR):
--   SELECT version_num FROM alembic_version;                  -- 020_white_label_branding_columns
--   SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
--     FROM information_schema.columns
--    WHERE table_name = 'white_label_configurations'
--      AND column_name IN ('branding_level', 'theme_mode', 'logo_dark_url', 'website_url',
--                          'accent_color', 'background_color', 'surface_color', 'text_color',
--                          'font_family', 'border_radius')
--    ORDER BY 1;
--     -- 10 rows, all character varying, is_nullable YES, column_default empty
--   SELECT count(*) FROM white_label_configurations;          -- unchanged by this file
