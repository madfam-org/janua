# Owner-exception hotfix image: production's janua-api plus the current OAuth
# reservation registry (see README.md in this folder).
# Base: the exact janua-api image production runs (the organization-role-shape
# hotfix pinned by janua#805). One layer, one file; nothing else is rebuilt or
# re-resolved.
FROM ghcr.io/madfam-org/janua-api@sha256:99f354a940f6a9ada0f899653445ee75682c101b9aba8525b06a0627301b8c0d
COPY --chown=janua:python apps/api/app/core/reserved_oauth_boundaries.py /app/app/core/
