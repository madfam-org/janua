# Owner-exception hotfix image: production's janua-api plus org-bound clients
# signing in platform-pool members of their own organization (janua#795; see
# README.md in this folder).
# Base: the exact janua-api image production runs (the ChatGPT-on-the-MAP
# hotfix pinned by janua#794). Two layers, two files; nothing else is rebuilt or
# re-resolved.
FROM ghcr.io/madfam-org/janua-api@sha256:ae28948d88cbd9dcb0ee3795ec881e9c8ddbb7e68103b0c83f937e3d003926e4
COPY --chown=janua:python apps/api/app/auth/tenant_login_context.py /app/app/auth/
COPY --chown=janua:python apps/api/app/auth/hosted_security.py /app/app/auth/
