# Owner-exception hotfix image: production's janua-api plus the operator-set
# primary organization (janua#822; see README.md in this folder).
# Base: the exact janua-api image production runs (the webhooks hotfix,
# janua#817, pinned by janua#818). Seven layers, seven files; nothing else is
# rebuilt or re-resolved. main.py is production's own main.py plus only the
# router registration (main.diff): main's main.py also carries janua#798.
FROM ghcr.io/madfam-org/janua-api@sha256:1b1e28de2e16d9672c5d536675f29a5784e556b5e0a14badfe2a999e7346c499
COPY --chown=janua:python apps/api/app/models/user_primary_organization.py /app/app/models/
COPY --chown=janua:python apps/api/app/schemas/primary_organization.py /app/app/schemas/
COPY --chown=janua:python apps/api/app/routers/v1/internal_primary_organization.py /app/app/routers/v1/
COPY --chown=janua:python apps/api/app/services/org_claims_service.py /app/app/services/
COPY --chown=janua:python apps/api/app/services/audit_logger.py /app/app/services/
COPY --chown=janua:python deployment/hotfix/janua-api-primary-organization/main.py /app/app/
COPY --chown=janua:python apps/api/alembic/versions/022_user_primary_organization.py /app/alembic/versions/
