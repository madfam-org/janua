# Owner-exception hotfix image: production's janua-api (row 14) plus janua#801's
# roles filter in the OIDC handler. See README.md in this folder.
# Base: the exact image production runs (row 14, pinned by janua#857). One layer:
# apps/api/app/routers/v1/oauth_provider_shared.py at SOURCE, replacing row 14's
# copy (deployment/hotfix/janua-api-edge-hardening/oauth_provider_shared.py.shipped).
FROM ghcr.io/madfam-org/janua-api@sha256:046d4686480e0eb73b6a5e8e1674b15936840eafcbc36fa1c5ee17ae702b0b2e
COPY --chown=janua:python apps/api/app/routers/v1/oauth_provider_shared.py /app/app/routers/v1/oauth_provider_shared.py
