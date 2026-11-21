# Owner-exception hotfix image: production's janua-api plus the nine merges after
# row 13 (janua#844, #845, #846, #847, #848, #850, #851, #852, #853). See
# README.md in this folder.
# Base: the exact janua-api image production runs (the login double-submit
# hotfix pinned by janua#843). Layer 1 lays apps/api/app at SOURCE (the
# workflow refuses a checkout whose apps/api/app is not SOURCE's) over the
# base; layers 2-8 put back the base's own copy of the seven files main changed
# before row 13 that no row ever shipped (kept_files.txt); layer 9 is
# oauth_provider_shared.py without janua#801's roles filter
# (oauth_provider_shared.py.shipped, oauth_provider_shared.diff). Nothing is
# rebuilt or re-resolved: no package, migration or setting changes.
FROM ghcr.io/madfam-org/janua-api@sha256:2bbee189303b669bb24302ed3437daa59ee2e0979436d79b3b02b887b1eeb361
COPY --chown=janua:python apps/api/app/ /app/app/
COPY --chown=janua:python --from=ghcr.io/madfam-org/janua-api@sha256:2bbee189303b669bb24302ed3437daa59ee2e0979436d79b3b02b887b1eeb361 /app/app/core/test_config.py /app/app/core/test_config.py
COPY --chown=janua:python --from=ghcr.io/madfam-org/janua-api@sha256:2bbee189303b669bb24302ed3437daa59ee2e0979436d79b3b02b887b1eeb361 /app/app/routers/v1/webhooks_dhanam.py /app/app/routers/v1/webhooks_dhanam.py
COPY --chown=janua:python --from=ghcr.io/madfam-org/janua-api@sha256:2bbee189303b669bb24302ed3437daa59ee2e0979436d79b3b02b887b1eeb361 /app/app/services/admin_notifications.py /app/app/services/admin_notifications.py
COPY --chown=janua:python --from=ghcr.io/madfam-org/janua-api@sha256:2bbee189303b669bb24302ed3437daa59ee2e0979436d79b3b02b887b1eeb361 /app/app/services/email_service.py /app/app/services/email_service.py
COPY --chown=janua:python --from=ghcr.io/madfam-org/janua-api@sha256:2bbee189303b669bb24302ed3437daa59ee2e0979436d79b3b02b887b1eeb361 /app/app/services/enhanced_email_service.py /app/app/services/enhanced_email_service.py
COPY --chown=janua:python --from=ghcr.io/madfam-org/janua-api@sha256:2bbee189303b669bb24302ed3437daa59ee2e0979436d79b3b02b887b1eeb361 /app/app/services/resend_email_service.py /app/app/services/resend_email_service.py
COPY --chown=janua:python --from=ghcr.io/madfam-org/janua-api@sha256:2bbee189303b669bb24302ed3437daa59ee2e0979436d79b3b02b887b1eeb361 /app/app/sso/application/services/product_tiers.py /app/app/sso/application/services/product_tiers.py
COPY --chown=janua:python deployment/hotfix/janua-api-edge-hardening/oauth_provider_shared.py.shipped /app/app/routers/v1/oauth_provider_shared.py
