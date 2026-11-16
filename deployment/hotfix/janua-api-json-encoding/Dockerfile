# Owner-exception hotfix image: production's janua-api plus the JSON column type
# that encodes once on PostgreSQL (see README.md in this folder).
# Base: the exact janua-api image production runs (the reservations-2 hotfix,
# janua#809, pinned by janua#813). One layer, one file; nothing else is rebuilt
# or re-resolved.
FROM ghcr.io/madfam-org/janua-api@sha256:78efc78925192d99f2116dbed27afcd46b9db96d27bcb7c029aaca73d681f858
COPY --chown=janua:python apps/api/app/models/types.py /app/app/models/
