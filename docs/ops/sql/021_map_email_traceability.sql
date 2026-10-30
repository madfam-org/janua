-- Reviewed native migration source; execution requires a named operator action.
-- Use Enclii's migration adapter. Record any missing adapter; never advance the
-- production ledger before reading back the actual database revision/schema.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL ROLE enclii;
DO $$
DECLARE n integer; v text;
BEGIN
  SELECT count(*), min(version_num) INTO n, v FROM alembic_version;
  IF n <> 1 OR v NOT IN ('020_org_authentication_policy', '021_map_email_traceability') THEN
    RAISE EXCEPTION 'expected alembic_version 020_org_authentication_policy or 021_map_email_traceability';
  END IF;
END $$;
CREATE TABLE IF NOT EXISTS email_send_audits (
  id UUID CONSTRAINT pk_email_send_audits PRIMARY KEY,
  magic_link_id UUID REFERENCES magic_links(id) ON DELETE RESTRICT,
  source_app VARCHAR(64) NOT NULL,
  message_kind VARCHAR(32) NOT NULL,
  trigger_kind VARCHAR(32) NOT NULL,
  provenance VARCHAR(40) NOT NULL,
  org_id VARCHAR(64),
  upstream_audit_id UUID,
  state VARCHAR(16) NOT NULL,
  provider_message_id VARCHAR(255),
  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  attempted_at TIMESTAMP WITHOUT TIME ZONE,
  accepted_at TIMESTAMP WITHOUT TIME ZONE,
  CONSTRAINT ck_email_send_audit_state CHECK (state IN ('pending','sending','accepted','rejected','unknown','not_issued')),
  CONSTRAINT ck_email_send_audit_receipt CHECK (state != 'accepted' OR (provider_message_id IS NOT NULL AND length(trim(provider_message_id)) > 0 AND accepted_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_email_send_audit_source_created ON email_send_audits(source_app, created_at);
CREATE INDEX IF NOT EXISTS ix_email_send_audit_upstream ON email_send_audits(upstream_audit_id);
CREATE INDEX IF NOT EXISTS ix_email_send_audit_provider ON email_send_audits(provider_message_id);
ALTER TABLE email_events ADD COLUMN IF NOT EXISTS mail_audit_id VARCHAR(36);
ALTER TABLE email_events ADD COLUMN IF NOT EXISTS map_audit_id VARCHAR(36);
ALTER TABLE email_events ADD COLUMN IF NOT EXISTS message_kind VARCHAR(32);
ALTER TABLE email_events ADD COLUMN IF NOT EXISTS trigger_kind VARCHAR(32);
ALTER TABLE email_events ADD COLUMN IF NOT EXISTS command_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS ix_email_events_mail_audit ON email_events(mail_audit_id);
ALTER TABLE payment_mail_dispatches ADD COLUMN IF NOT EXISTS map_audit_id VARCHAR(36);
GRANT SELECT, INSERT, UPDATE ON email_send_audits TO janua;
UPDATE alembic_version SET version_num = '021_map_email_traceability'
WHERE version_num = '020_org_authentication_policy';
COMMIT;
