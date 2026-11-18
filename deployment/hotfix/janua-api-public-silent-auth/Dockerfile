# Owner-exception hotfix image: production's janua-api plus janua#833 (a public
# client an operator marked with madfam:silent_auth may use prompt=none and skip
# the consent screen, under per-request conditions). See README.md in this
# folder.
# Base: the exact janua-api image production runs (the hosted-locale hotfix
# pinned by janua#831). One layer, one file; nothing else is rebuilt or
# re-resolved. oauth_provider.py is production's own copy (the hosted-locale
# hotfix's oauth_provider.py.shipped) plus only janua#833's hunks
# (oauth_provider.diff): main's also carries janua#792 and janua#801. It is kept
# here as oauth_provider.py.shipped so code scanning does not re-report, on a
# second path, the alerts it already tracks on
# apps/api/app/routers/v1/oauth_provider.py.
FROM ghcr.io/madfam-org/janua-api@sha256:b9396f85e85e6f233cac090a032026f12540881848122e6ddfd68600a3dcae1a
COPY --chown=janua:python deployment/hotfix/janua-api-public-silent-auth/oauth_provider.py.shipped /app/app/routers/v1/oauth_provider.py
