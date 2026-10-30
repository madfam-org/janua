-- Additive organization-policy/session-assurance schema for reviewed native migration.
-- No production execution is authorized by this file. Use the approved Enclii
-- migration path; keep release held when its typed adapter is unavailable.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL ROLE enclii;
DO $$
DECLARE n integer; v text;
BEGIN
  SELECT count(*), min(version_num) INTO n, v FROM alembic_version;
  IF n <> 1 OR v NOT IN ('019_email_first_party_engagement', '020_org_authentication_policy') THEN
    RAISE EXCEPTION 'expected alembic_version 019_email_first_party_engagement or 020_org_authentication_policy';
  END IF;
END $$;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS authentication_methods JSONB NOT NULL DEFAULT '[]';
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS authenticated_at TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS mfa_verified_at TIMESTAMP WITHOUT TIME ZONE;
CREATE TABLE IF NOT EXISTS organization_authentication_policies (
  organization_id UUID PRIMARY KEY REFERENCES organizations(id),
  mfa_mode VARCHAR(16) NOT NULL,
  version INTEGER NOT NULL,
  updated_by UUID NOT NULL REFERENCES users(id),
  updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  CONSTRAINT ck_org_auth_policy_mfa_mode CHECK (mfa_mode IN ('optional', 'required')),
  CONSTRAINT ck_org_auth_policy_version CHECK (version >= 1)
);
CREATE TABLE IF NOT EXISTS organization_authentication_policy_changes (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id),
  version INTEGER NOT NULL,
  previous_mode VARCHAR(16) NOT NULL,
  mfa_mode VARCHAR(16) NOT NULL,
  actor_id UUID NOT NULL REFERENCES users(id),
  reason VARCHAR(300) NOT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  CONSTRAINT uq_org_auth_policy_change_version UNIQUE (organization_id, version),
  CONSTRAINT ck_org_auth_change_mfa_mode CHECK (mfa_mode IN ('optional', 'required')),
  CONSTRAINT ck_org_auth_change_previous_mode CHECK (previous_mode IN ('optional', 'required'))
);
GRANT SELECT, INSERT, UPDATE ON organization_authentication_policies TO janua;
GRANT SELECT, INSERT ON organization_authentication_policy_changes TO janua;
UPDATE alembic_version SET version_num = '020_org_authentication_policy'
WHERE version_num = '019_email_first_party_engagement';
COMMIT;
