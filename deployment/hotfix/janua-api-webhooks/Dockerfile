# Owner-exception hotfix image: production's janua-api plus the webhook service
# ported to the async session (see README.md in this folder).
# Base: the exact janua-api image production runs (the JSON-encoding hotfix,
# janua#815, pinned by janua#816). Two layers, two files; nothing else is
# rebuilt or re-resolved.
FROM ghcr.io/madfam-org/janua-api@sha256:9bac921211d652922f61571e9d1129da19df49725067bfabbd0e67b224910c2c
COPY --chown=janua:python apps/api/app/services/webhooks.py /app/app/services/
COPY --chown=janua:python apps/api/app/routers/v1/webhooks.py /app/app/routers/v1/
