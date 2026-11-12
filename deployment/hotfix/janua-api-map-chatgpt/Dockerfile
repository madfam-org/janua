# Owner-exception hotfix image: production's janua-api plus ChatGPT on the MAP
# de Crea Tu Mundo protected resource (see README.md in this folder).
# Base: the exact janua-api image production runs (the reserved-boundaries
# hotfix pinned by janua#789). Two layers, two files, one per folder; nothing
# else is rebuilt or re-resolved.
FROM ghcr.io/madfam-org/janua-api@sha256:b6e16fa59433bb9f4bdc662c3a0e9d20fb55dca3f546d2b016f2346d41c80d72
COPY --chown=janua:python apps/api/app/core/protected_resources.py /app/app/core/
COPY --chown=janua:python apps/api/app/services/client_id_metadata.py /app/app/services/
