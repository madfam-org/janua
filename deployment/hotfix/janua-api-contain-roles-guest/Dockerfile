# Owner-exception hotfix image: production's janua-api plus janua#826 (product
# role scopes reserved; guest tokens carry their own audience). See README.md
# in this folder.
# Base: the exact janua-api image production runs (the primary-organization
# hotfix pinned by janua#824). Two layers, two files; nothing else is rebuilt
# or re-resolved.
FROM ghcr.io/madfam-org/janua-api@sha256:cd6e19df31f412fe3530c7481af8de1c4263b7ae0830795ab9d392737a0da9f5
COPY --chown=janua:python apps/api/app/core/reserved_oauth_boundaries.py /app/app/core/
COPY --chown=janua:python apps/api/app/routers/v1/guest.py /app/app/routers/v1/
