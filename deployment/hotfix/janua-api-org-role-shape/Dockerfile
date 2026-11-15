# Owner-exception hotfix image: production's janua-api plus the rule that an
# organization role is never published as an application role (janua#801,
# janua#802; see README.md in this folder).
# Base: the exact janua-api image production runs (the org-bound-login hotfix
# pinned by janua#797). Three layers, three files; nothing else is rebuilt or
# re-resolved.
FROM ghcr.io/madfam-org/janua-api@sha256:f97bddd83a8091ed17c9c33d8ee36577406afefa902c35cd8e42c2f7dff8326e
COPY --chown=janua:python apps/api/app/services/org_claims_service.py /app/app/services/
COPY --chown=janua:python apps/api/app/services/role_service.py /app/app/services/
COPY --chown=janua:python apps/api/app/services/organization_member_service.py /app/app/services/
