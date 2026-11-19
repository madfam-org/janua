# Owner-exception hotfix image: production's janua-api plus janua#841 (a second
# sign-in POST for an already-used pending request lands in the application or
# on a GET «expired» page instead of the raw JSON error body, and every hosted
# form loads a same-origin one-press script). See README.md in this folder.
# Base: the exact janua-api image production runs (the public-silent-auth
# hotfix pinned by janua#835). Three layers, three files; nothing else is
# rebuilt or re-resolved. Production's copy of each file is byte-identical to
# its copy on main before janua#841 (hosted_locale.py and auth.py at
# HOSTED_SOURCE, tenant_login_context.py at ORG_LOGIN_SOURCE), so the files are
# main's, and each differs from production's by exactly janua#841's hunks
# (hosted_locale.diff, tenant_login_context.diff, auth.diff).
FROM ghcr.io/madfam-org/janua-api@sha256:44c4310d742f4720efca7158872a88497fee6fd910996635109353ba7e098678
COPY --chown=janua:python apps/api/app/auth/hosted_locale.py /app/app/auth/
COPY --chown=janua:python apps/api/app/auth/tenant_login_context.py /app/app/auth/
COPY --chown=janua:python apps/api/app/routers/v1/auth.py /app/app/routers/v1/
