# Owner-exception hotfix image: production's janua-api (row 15) plus janua#860,
# which makes `expires_in` announce the access token's real lifetime.
# See README.md in this folder.
# Base: the exact image production runs (row 15, pinned by janua#859). One layer:
# apps/api/app/routers/v1/oauth_provider_grants.py at SOURCE, replacing
# production's copy (the same file at ae191e86).
FROM ghcr.io/madfam-org/janua-api@sha256:0b8b5cfd91e95a82ab4508c083e34edc364338a61df8b2af19a76babda521989
COPY --chown=janua:python apps/api/app/routers/v1/oauth_provider_grants.py /app/app/routers/v1/oauth_provider_grants.py
