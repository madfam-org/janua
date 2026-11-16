# Owner-exception hotfix image: production's janua-api plus the current OAuth
# reservation registry (see README.md in this folder).
# Base: the exact janua-api image production runs (the entitlement-source
# hotfix, janua#811, pinned after janua#805's organization-role-shape image).
# One layer, one file; nothing else is rebuilt or re-resolved.
FROM ghcr.io/madfam-org/janua-api@sha256:cf723284080b94d78419c8cd2a189e8ecffe9b5a24c79e7b60e60bd0fa528032
COPY --chown=janua:python apps/api/app/core/reserved_oauth_boundaries.py /app/app/core/
