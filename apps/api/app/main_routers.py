"""Janua API router imports and registration (split out of app/main.py).

Moved verbatim on 2026-11-19 to keep app/main.py under the repository's
800-line pre-commit limit; no behaviour change. `app.main` imports this module
at the point where it used to import the routers (same import order) and calls
`include_routers(app)` where it used to include them (same route order). The
optional-router warnings keep logging under the `app.main` logger name.
"""

import logging

logger = logging.getLogger("app.main")

from app.routers.v1 import (
    admin as admin_v1,
)
from app.routers.v1 import (
    alerts as alerts_v1,
)
from app.routers.v1 import (
    api_keys as api_keys_v1,
)
from app.routers.v1 import (
    audit_logs as audit_logs_v1,
)
from app.routers.v1 import (
    auth as auth_v1,
)
from app.routers.v1 import (
    billing as billing_v1,
)
from app.routers.v1 import (
    connections as connections_v1,
)
from app.routers.v1 import (
    connections_consent as connections_consent_v1,
)
from app.routers.v1 import (
    device_enrolment as device_enrolment_v1,
)
from app.routers.v1 import (
    devices as devices_v1,
)
from app.routers.v1 import (
    guest as guest_v1,
)
from app.routers.v1 import (
    guest_invites as guest_invites_v1,
)
from app.routers.v1 import (
    integrations as integrations_v1,
)
from app.routers.v1 import (
    invitations as invitations_v1,
)
from app.routers.v1 import (
    localization as localization_v1,
)
from app.routers.v1 import (
    me as me_v1,
)
from app.routers.v1 import (
    mfa as mfa_v1,
)
from app.routers.v1 import (
    oauth as oauth_v1,
)
from app.routers.v1 import (
    oauth_clients as oauth_clients_v1,
)
from app.routers.v1 import (
    oauth_on_behalf as oauth_on_behalf_v1,
)
from app.routers.v1 import (
    oauth_provider as oauth_provider_v1,
)
from app.routers.v1 import (
    organization_app_roles as organization_app_roles_v1,
)
from app.routers.v1 import (
    organization_members as organization_members_v1,
)
from app.routers.v1 import (
    organizations as organizations_v1,
)
from app.routers.v1 import (
    passkeys as passkeys_v1,
)
from app.routers.v1 import (
    policies as policies_v1,
)
from app.routers.v1 import (
    rbac as rbac_v1,
)
from app.routers.v1 import (
    roles as roles_v1,
)
from app.routers.v1 import (
    sessions as sessions_v1,
)
from app.routers.v1 import (
    users as users_v1,
)
from app.routers.v1 import (
    webhooks as webhooks_v1,
)
from app.routers.v1 import (
    webhooks_dhanam as webhooks_dhanam_v1,
)

# Additional feature routers with optional loading
additional_routers = {}
try:
    from app.routers.v1 import graphql as graphql_v1

    additional_routers["graphql"] = graphql_v1
except Exception as e:
    logger.warning(f"GraphQL router not available: {e}")

try:
    from app.routers.v1 import websocket as websocket_v1

    additional_routers["websocket"] = websocket_v1
except Exception as e:
    logger.warning(f"WebSocket router not available: {e}")

try:
    from app.routers.v1 import iot as iot_v1

    additional_routers["iot"] = iot_v1
except Exception as e:
    logger.warning(f"IoT router not available: {e}")

# Enterprise routers with optional loading for production stability
enterprise_routers = {}
try:
    from app.routers.v1 import sso as sso_v1

    enterprise_routers["sso"] = sso_v1
except Exception as e:
    logger.warning(f"SSO router not available: {e}")

# SSO DDD module routers (enterprise implementation)
try:
    from app.sso.routers import configuration as sso_config
    from app.sso.routers import metadata as sso_metadata
    from app.sso.routers import oidc as sso_oidc

    enterprise_routers["sso_oidc"] = sso_oidc
    enterprise_routers["sso_config"] = sso_config
    enterprise_routers["sso_metadata"] = sso_metadata
except Exception as e:
    logger.warning(f"SSO DDD routers not available: {e}")

try:
    from app.routers.v1 import migration as migration_v1

    enterprise_routers["migration"] = migration_v1
except Exception as e:
    logger.warning(f"Migration router not available: {e}")

try:
    from app.routers.v1 import white_label as white_label_v1

    enterprise_routers["white_label"] = white_label_v1
except Exception as e:
    logger.warning(f"White label router not available: {e}")

try:
    from app.routers.v1 import compliance as compliance_v1

    enterprise_routers["compliance"] = compliance_v1
except Exception as e:
    logger.warning(f"Compliance router not available: {e}")

try:
    from app.routers.v1 import scim as scim_v1

    enterprise_routers["scim"] = scim_v1
except Exception as e:
    logger.warning(f"SCIM router not available: {e}")

try:
    from app.routers.v1 import scim_config as scim_config_v1

    enterprise_routers["scim_config"] = scim_config_v1
except Exception as e:
    logger.warning(f"SCIM Config router not available: {e}")


def include_routers(app) -> None:
    """Register every router on `app`, in the order app/main.py always used."""
    # Import health router and inject health checker
    from app.routers.v1 import health as health_v1

    # Include v1 routers
    app.include_router(health_v1.router, prefix="/api/v1")
    app.include_router(auth_v1.router, prefix="/api/v1")
    app.include_router(oauth_v1.router, prefix="/api/v1")
    app.include_router(oauth_clients_v1.router, prefix="/api/v1")
    app.include_router(oauth_provider_v1.router, prefix="/api/v1")
    app.include_router(oauth_provider_v1.logout_router)
    # P3.2 — on-behalf OAuth linking for Enclii self-serve signup.
    # Endpoints no-op with 404 unless JANUA_SERVICE_TOKEN is configured.
    app.include_router(oauth_on_behalf_v1.router, prefix="/api/v1")
    app.include_router(users_v1.router, prefix="/api/v1")
    app.include_router(sessions_v1.router, prefix="/api/v1")
    app.include_router(devices_v1.router, prefix="/api/v1")
    # Shared devices (OAuth clients of kind "device"): the public register/poll
    # routes a device calls before it has a credential, and the organization
    # administrators' approve/list/disable routes. Imported at module top, so a
    # broken router fails startup instead of silently dropping the surface.
    app.include_router(device_enrolment_v1.public_router, prefix="/api/v1")
    app.include_router(device_enrolment_v1.admin_router, prefix="/api/v1")
    app.include_router(organizations_v1.router, prefix="/api/v1")
    app.include_router(organization_members_v1.router, prefix="/api/v1")
    # Delegated app-role administration: an `<app>:admin` manages that app's roles
    # in their own org (user token). Imported at module top, so a broken router
    # fails startup instead of silently dropping the surface.
    app.include_router(organization_app_roles_v1.router, prefix="/api/v1")
    app.include_router(rbac_v1.router, prefix="/api/v1")
    app.include_router(mfa_v1.router, prefix="/api/v1")
    app.include_router(passkeys_v1.router, prefix="/api/v1")
    app.include_router(admin_v1.router, prefix="/api/v1")
    app.include_router(webhooks_v1.router, prefix="/api/v1")
    app.include_router(webhooks_dhanam_v1.router, prefix="/api/v1")
    app.include_router(integrations_v1.router, prefix="/api/v1")
    app.include_router(connections_v1.router, prefix="/api/v1")
    app.include_router(connections_consent_v1.router, prefix="/api/v1")
    app.include_router(api_keys_v1.router, prefix="/api/v1")
    app.include_router(roles_v1.router, prefix="/api/v1")

    # Dhanam checkout router (for MADFAM billing integration)
    try:
        from app.routers.v1 import checkout_dhanam as checkout_dhanam_v1

        app.include_router(checkout_dhanam_v1.router, prefix="/api/v1")
        logger.info("Registered Dhanam checkout router successfully")
    except Exception as e:
        logger.warning(f"Dhanam checkout router not available: {e}")

    # Register newly added core routers
    app.include_router(policies_v1.router, prefix="/api")
    app.include_router(invitations_v1.router, prefix="/api")
    app.include_router(audit_logs_v1.router, prefix="/api")
    app.include_router(alerts_v1.router, prefix="/api/v1")
    app.include_router(localization_v1.router, prefix="/api/v1")  # Localization model now available
    app.include_router(billing_v1.router, prefix="/api/v1")  # Billing and plans
    app.include_router(guest_v1.router, prefix="/api/v1")  # Guest access tokens
    app.include_router(guest_invites_v1.router, prefix="/api/v1")  # Guest invite CRUD
    app.include_router(me_v1.router, prefix="/api/v1")  # Caller-scoped (entitlements)

    # Narrow service-token mail boundary; registration failures must fail startup.
    from app.routers.v1 import payment_notices as payment_notices_v1

    app.include_router(payment_notices_v1.router, prefix="/api/v1")

    # Resend webhooks (public, Svix-signed) and the per-app events feed they fill
    # (internal-key). Registration failures must fail startup: a silently missing
    # receiver makes Resend retry into a 404 until it disables the endpoint.
    from app.routers.v1 import email_webhooks as email_webhooks_v1
    from app.routers.v1 import internal_email_audit as internal_email_audit_v1
    from app.routers.v1 import internal_email_events as internal_email_events_v1
    from app.routers.v1 import internal_email_usage as internal_email_usage_v1

    app.include_router(email_webhooks_v1.router, prefix="/api/v1")
    app.include_router(internal_email_events_v1.router, prefix="/api/v1/internal")
    app.include_router(internal_email_audit_v1.router, prefix="/api/v1/internal")
    # Per-account quota usage, counted from the same stored `email.sent` events.
    app.include_router(internal_email_usage_v1.router, prefix="/api/v1/internal")

    # First-party open pixel / click redirect (public, no auth, not in the schema),
    # served on each binding's tracking host (CTM_TRACKING_HOST). Mounted at the
    # root: `/e/o/{token}.gif`, `/e/c/{token}/{index}`. Registration failures must
    # fail startup: a missing redirect would break links in delivered mail.
    from app.routers.v1 import email_engagement as email_engagement_v1

    app.include_router(email_engagement_v1.router)

    # Render-only preview of what /internal/email/send{,-template} would hand to
    # Resend (same renderer, same sender resolution, same token-link rule).
    from app.routers.v1 import email_preview as email_preview_v1

    app.include_router(email_preview_v1.router, prefix="/api/v1/internal")

    # Internal service API routers (for MADFAM service-to-service communication)
    try:
        from app.routers.v1 import email as email_v1

        app.include_router(email_v1.router, prefix="/api/v1/internal")
        logger.info("Registered internal email router successfully")
    except Exception as e:
        logger.warning(f"Email router not available: {e}")

    # Internal user lifecycle (sibling-app roster provisioning: crea-map alta/baja)
    try:
        from app.routers.v1 import internal_users as internal_users_v1

        app.include_router(internal_users_v1.router, prefix="/api/v1/internal")
        logger.info("Registered internal users router successfully")
    except Exception as e:
        logger.warning(f"Internal users router not available: {e}")

    # Internal capability links (subject-scoped bearer grants for sibling apps)
    try:
        from app.routers.v1 import internal_capability_links as internal_capability_links_v1

        app.include_router(internal_capability_links_v1.router, prefix="/api/v1/internal")
        logger.info("Registered internal capability links router successfully")
    except Exception as e:
        logger.warning(f"Internal capability links router not available: {e}")

    # Internal application roles (per-org `hcm:*` grants that reach the `roles` claim)
    try:
        from app.routers.v1 import internal_app_roles as internal_app_roles_v1

        app.include_router(internal_app_roles_v1.router, prefix="/api/v1/internal")
        logger.info("Registered internal app roles router successfully")
    except Exception as e:
        logger.warning(f"Internal app roles router not available: {e}")

    # Internal primary organization (operator-set: which of a multi-org person's
    # memberships their tokens speak for, so its app roles can reach `roles`)
    try:
        from app.routers.v1 import internal_primary_organization as internal_primary_organization_v1

        app.include_router(internal_primary_organization_v1.router, prefix="/api/v1/internal")
        logger.info("Registered internal primary organization router successfully")
    except Exception as e:
        logger.warning(f"Internal primary organization router not available: {e}")

    # Internal by-org entitlement read (the VIEWED WORKSPACE's org tiles, for the
    # nauta ERP advisor case: a service credential reads an org's entitlements by id,
    # where `/me/entitlements` can only answer for the calling user)
    try:
        from app.routers.v1 import internal_org_entitlements as internal_org_entitlements_v1

        app.include_router(internal_org_entitlements_v1.router, prefix="/api/v1/internal")
        logger.info("Registered internal org entitlements router successfully")
    except Exception as e:
        logger.warning(f"Internal org entitlements router not available: {e}")

    # Internal OAuth-client scope grants (`allowed_scopes` IS a service client's
    # grant record: an org-bound client's namespaced scopes become `roles` app roles)
    try:
        from app.routers.v1 import (
            internal_oauth_client_scopes as internal_oauth_client_scopes_v1,
        )

        app.include_router(internal_oauth_client_scopes_v1.router, prefix="/api/v1/internal")
        logger.info("Registered internal oauth client scopes router successfully")
    except Exception as e:
        logger.warning(f"Internal oauth client scopes router not available: {e}")

    # Internal product invitations (invite-only clients: grant the client's product,
    # mail ONE sign-in link) and the public entry route the link lands on.
    try:
        from app.routers.v1 import internal_product_invites as internal_product_invites_v1

        app.include_router(internal_product_invites_v1.router, prefix="/api/v1/internal")
        app.include_router(internal_product_invites_v1.entry_router, prefix="/api/v1")
        logger.info("Registered internal product invites router successfully")
    except Exception as e:
        logger.warning(f"Internal product invites router not available: {e}")

    # Internal role/tier sync router (Dhanam → Janua hub-and-spoke)
    try:
        from app.routers.internal import roles as internal_roles

        app.include_router(internal_roles.router, prefix="/internal")
        logger.info("Registered internal roles router successfully")
    except Exception as e:
        logger.warning(f"Internal roles router not available: {e}")

    # Register additional feature routers if available
    for router_name, router_module in additional_routers.items():
        try:
            app.include_router(router_module.router, prefix="/api/v1")
            logger.info(f"Registered {router_name} router successfully")
        except Exception as e:
            logger.error(f"Failed to register {router_name} router: {e}")

    # Register enterprise routers if available
    for router_name, router_module in enterprise_routers.items():
        try:
            app.include_router(router_module.router, prefix="/api/v1")
            logger.info(f"Registered {router_name} router successfully")
        except Exception as e:
            logger.error(f"Failed to register {router_name} router: {e}")
