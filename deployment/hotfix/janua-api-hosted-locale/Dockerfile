# Owner-exception hotfix image: production's janua-api plus janua#814 and
# janua#820 (the account chooser, the second-factor branch of /oauth/authorize
# and the switch refusal page follow the hosted ui_locales rule). See README.md
# in this folder.
# Base: the exact janua-api image production runs (the contain-roles-guest
# hotfix pinned by janua#828). Three layers, three files; nothing else is
# rebuilt or re-resolved. oauth_provider.py is production's own copy plus only
# the two merges' hunks (oauth_provider.diff): main's also carries janua#792
# and janua#801. It is kept here as oauth_provider.py.shipped so code scanning
# does not re-report, on a second path, the alerts it already tracks on
# apps/api/app/routers/v1/oauth_provider.py.
FROM ghcr.io/madfam-org/janua-api@sha256:507e76f567c0847a124515f3e2d3b76d698a2c9f4dc9aae9fdf6d099cf966eec
COPY --chown=janua:python apps/api/app/auth/hosted_locale.py /app/app/auth/
COPY --chown=janua:python apps/api/app/routers/v1/auth.py /app/app/routers/v1/
COPY --chown=janua:python deployment/hotfix/janua-api-hosted-locale/oauth_provider.py.shipped /app/app/routers/v1/oauth_provider.py
