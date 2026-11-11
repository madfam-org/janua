# Owner-exception hotfix image: production's janua-api plus the reviewed OAuth
# reservation registry (see README.md in this folder).
# Base: the exact janua-api image production runs, built from b16869d7.
# One layer, two files; nothing else is rebuilt or re-resolved.
FROM ghcr.io/madfam-org/janua-api@sha256:7c9076615ad8345c88b8093e660a4484dd3ff6f0b9d43b11c28a9d85c5884676
COPY --chown=janua:python apps/api/app/core/oauth_metadata.py apps/api/app/core/reserved_oauth_boundaries.py /app/app/core/
