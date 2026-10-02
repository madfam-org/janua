# Data-subject request exports: access rule and audit

## The rule

`GET /api/v1/compliance/data-subject-request/{request_id}/data` returns a
data-subject request export (GDPR Article 15) only when the caller is:

- the request's own data subject, or
- a platform administrator (`users.is_admin`, the same check as the
  compliance admin routes).

Any other caller gets **the same 404 as an unknown request id**, so the
response does not reveal that the request exists, and the request is left
unchanged. Organization administrators who are not platform administrators
follow the same rule as any other user: the RBAC model has no
organization-level compliance permission.

Where the rule lives: `DataSubjectRightsService.get_request_for_processor` in
`apps/api/app/services/compliance_service.py`. Both `process_access_request`
and `process_erasure_request` use it and default to a non-administrator
processor. The router passes `processor_is_admin` from the caller
(`apps/api/app/routers/v1/compliance.py`). `POST /compliance/data-subject-request`
creates a request for the caller only.

Tests:

- `apps/api/tests/unit/routers/test_compliance_dsr_access_scope.py`: the real
  router on SQLite. The subject gets 200; another user, an organization
  administrator and an unknown id get the same 404; a platform administrator
  gets 200.
- `apps/api/tests/unit/services/test_compliance_dsr_processor_scope.py`: the
  service rule for access and erasure.
- `apps/api/tests/unit/test_audit_data_subject_request_access.py`: the audit
  script below, including a real-PostgreSQL run in the PostgreSQL CI job
  (`database` marker).

## Audit: who processed existing requests

`apps/api/scripts/audit_data_subject_request_access.py` is read-only. It runs
in one `READ ONLY` transaction and prints **counts only**: no ids, emails or
personal data.

It reports:

- data-subject requests by type and by status;
- per type, who last processed each request: `not_processed`, `subject`,
  `platform_admin`, `other_user` or `missing_user`;
- audit-log rows about data-subject requests, by action;
- `not_knowable`: what the schema cannot answer (see below).

```bash
# From apps/api, with DIRECT_DATABASE_URL or DATABASE_URL set (never printed)
python scripts/audit_data_subject_request_access.py           # text
python scripts/audit_data_subject_request_access.py --json    # one JSON object

# In a pod, piped on stdin (the script is self-contained)
kubectl -n janua exec -i deploy/janua-api -- python - --json \
  < apps/api/scripts/audit_data_subject_request_access.py
```

Exit status: `0` when every processed request was last processed by its
subject or a platform administrator; `2` when at least one was last processed
by another user or by a user row that no longer exists; `1` on error.

### What the audit cannot tell

- `assigned_to` keeps only the **last** processor. A later export by the
  subject hides an earlier export by someone else.
- The export path writes no audit-log row, so no table records each export,
  who made it, or how many times a request was exported.
- `users.is_admin` is read as it is today, not as it was at export time.

An exit status of `2` is a finding for the owner to review, not proof of
disclosure. Closing these gaps needs an audit-log row on every export, which
is not part of this change.
