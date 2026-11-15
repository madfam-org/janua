# Owner-exception hotfix image: production's janua-api plus the current OAuth
# reservation registry (see README.md in this folder).
# Base: the exact janua-api image production runs (the org-bound login hotfix
# pinned by janua#797). One layer, one file; nothing else is rebuilt or
# re-resolved.
FROM ghcr.io/madfam-org/janua-api@sha256:f97bddd83a8091ed17c9c33d8ee36577406afefa902c35cd8e42c2f7dff8326e
COPY --chown=janua:python apps/api/app/core/reserved_oauth_boundaries.py /app/app/core/
