"""The MCP-vs-API coverage contract for the janua MCP pilot.

P1 of the 2026-09-22 ecosystem strategic priorities requires that every service's
API set has an MCP equivalent, and that a *guard test ties the MCP tool set to the
API schema so drift fails CI*. This module is that contract's source of truth.

It declares, explicitly and by hand:

* ``PILOT_SCOPE`` -- the API paths the pilot MCP server MUST expose as tools. Every
  one of these is checked against both the live OpenAPI schema (it must still exist
  on the API) and the generated tool registry (it must have a tool). A new endpoint
  added to the pilot scope with no tool fails the guard.

* ``INTENDED_SURFACE`` -- the *full* internal surface this pilot is a slice of. The
  guard walks the whole ``/api/v1/internal`` prefix in the OpenAPI schema and asserts
  every path is either in ``PILOT_SCOPE`` (covered) or in ``EXEMPTIONS`` (a written,
  reasoned deferral). A brand-new internal endpoint that is neither covered nor
  exempted fails CI -- which is exactly the "a future new endpoint without an MCP
  tool fails CI" property the roadmap names.

* ``EXEMPTIONS`` -- endpoints deliberately left out of the pilot, each with a reason.
  The destructive / credentialed internal endpoints (user deprovisioning, app-role
  and capability grants, entitlement writes) are exempted here: they carry the same
  ``X-Internal-API-Key`` gate as email over HTTP, but exposing them as MCP tools is a
  later, operator-gated slice (see the roadmap's "destructive/credentialed endpoints
  keep operator gates" constraint). They are named, not silently dropped.

Why the internal-*email* surface is the pilot slice (and not the whole ~467-route
janua API): it is the cleanest self-contained sub-surface -- four endpoints behind a
single uniform auth gate (``verify_internal_api_key``), well-documented
(``docs/MADFAM_EMAIL_INTEGRATION.md``), and none of the four is itself irreversible
in the way ``internal_users`` deprovisioning or a fiscal stamp is. It lets the pilot
prove the generator + auth-passthrough + drift-guard pattern end to end without
taking on the whole surface at once. The other internal routers, and eventually the
end-user (JWT) surface, are follow-on slices.
"""

from __future__ import annotations

from dataclasses import dataclass

# The OpenAPI prefix that scopes this pilot. The email router mounts at
# ``/api/v1/internal`` (app/main.py) with its own ``/email`` prefix, so every pilot
# path lives under this. The guard treats this prefix as the "intended surface"
# boundary: everything under it must be covered or exempted.
INTERNAL_PREFIX = "/api/v1/internal"


@dataclass(frozen=True)
class Endpoint:
    """One (method, path) the pilot cares about, and the tool that stands for it."""

    method: str
    path: str
    tool_name: str
    summary: str


# ---------------------------------------------------------------------------
# Covered: the pilot MUST expose an MCP tool for each of these.
# ---------------------------------------------------------------------------
PILOT_SCOPE: tuple[Endpoint, ...] = (
    Endpoint(
        method="POST",
        path=f"{INTERNAL_PREFIX}/email/send",
        tool_name="janua_email_send",
        summary="Send a custom transactional email through janua (Resend-backed).",
    ),
    Endpoint(
        method="POST",
        path=f"{INTERNAL_PREFIX}/email/send-template",
        tool_name="janua_email_send_template",
        summary="Send a transactional email from janua's server-side template registry.",
    ),
    Endpoint(
        method="GET",
        path=f"{INTERNAL_PREFIX}/email/templates",
        tool_name="janua_email_list_templates",
        summary="List the transactional email templates janua can render.",
    ),
    Endpoint(
        method="GET",
        path=f"{INTERNAL_PREFIX}/email/health",
        tool_name="janua_email_health",
        summary="Report whether janua's email subsystem is configured and healthy.",
    ),
    # Read-only / render-only additions (2026-09-23): the per-app Resend events
    # feed and the send preview. Neither sends, writes or grants anything.
    Endpoint(
        method="GET",
        path=f"{INTERNAL_PREFIX}/email/events",
        tool_name="janua_email_events_feed",
        summary=(
            "Read delivered/opened/clicked/bounced events for one sending app's mail, "
            "cursor-paginated (no recipient data)."
        ),
    ),
    Endpoint(
        method="POST",
        path=f"{INTERNAL_PREFIX}/email/preview",
        tool_name="janua_email_preview",
        summary=(
            "Render exactly what a send or template send would hand to Resend "
            "(subject, resolved From, bodies) without sending."
        ),
    ),
    Endpoint(
        method="GET",
        path=f"{INTERNAL_PREFIX}/email/preview/templates",
        tool_name="janua_email_preview_templates",
        summary="List previewable templates with their required context variables.",
    ),
)


@dataclass(frozen=True)
class Exemption:
    """An internal endpoint deliberately NOT in the pilot, with a written reason."""

    method: str
    path: str
    reason: str


# ---------------------------------------------------------------------------
# Exempted: named, reasoned deferrals. These keep their HTTP auth gate; the point
# of listing them is that the guard REQUIRES a decision -- cover or exempt -- for
# every internal endpoint, so nothing is dropped by silence.
#
# The destructive/credentialed ones are the roadmap's "operator-gated" cases: an
# MCP tool for them must carry an operator-confirmation step, which this pilot slice
# does not build. They are follow-on work, flagged here so the guard stays honest.
# ---------------------------------------------------------------------------
_DESTRUCTIVE = (
    "Destructive/credentialed internal endpoint. Deferred from the pilot: an MCP tool "
    "for it must carry the same operator gate the roadmap requires for irreversible/"
    "credentialed actions (agent prepares, operator fires). Follow-on slice."
)
_READ_OR_GRANT = (
    "Internal identity/entitlement endpoint outside the email slice. Deferred to a "
    "later internal-surface slice; grants and writes here are credentialed and will "
    "need the operator-gate treatment before becoming tools."
)

# Path templates below match the live janua OpenAPI (the guard walks the schema and
# requires every internal path to be covered or exempted -- these are verified against
# it, not guessed).
EXEMPTIONS: tuple[Exemption, ...] = (
    # internal_users -- user lifecycle (provision / suspend are credentialed and
    # effectively irreversible for the affected principal; reactivate restores).
    Exemption("POST", f"{INTERNAL_PREFIX}/users/provision", _DESTRUCTIVE),
    Exemption("POST", f"{INTERNAL_PREFIX}/users/suspend", _DESTRUCTIVE),
    Exemption("POST", f"{INTERNAL_PREFIX}/users/reactivate", _DESTRUCTIVE),
    # internal_app_roles -- app-role grants that flow into JWT `roles`.
    Exemption("POST", f"{INTERNAL_PREFIX}/app-roles/grant", _READ_OR_GRANT),
    Exemption("POST", f"{INTERNAL_PREFIX}/app-roles/revoke", _DESTRUCTIVE),
    Exemption(
        "GET", f"{INTERNAL_PREFIX}/app-roles/{{organization_id}}/{{user_id}}", _READ_OR_GRANT
    ),
    # internal_capability_links -- capability grants between orgs/apps.
    Exemption("POST", f"{INTERNAL_PREFIX}/capability-links", _READ_OR_GRANT),
    Exemption("POST", f"{INTERNAL_PREFIX}/capability-links/resolve", _READ_OR_GRANT),
    Exemption("POST", f"{INTERNAL_PREFIX}/capability-links/{{link_id}}/revoke", _DESTRUCTIVE),
    Exemption("POST", f"{INTERNAL_PREFIX}/capability-links/{{link_id}}/rotate", _DESTRUCTIVE),
    # internal_oauth_client_scopes -- OAuth client scope grants.
    Exemption("GET", f"{INTERNAL_PREFIX}/oauth-clients/{{client_id}}/scopes", _READ_OR_GRANT),
    Exemption("POST", f"{INTERNAL_PREFIX}/oauth-clients/{{client_id}}/scopes", _READ_OR_GRANT),
    Exemption("POST", f"{INTERNAL_PREFIX}/oauth-clients/{{client_id}}/scopes/revoke", _DESTRUCTIVE),
    # internal_org_entitlements -- entitlement read.
    Exemption("GET", f"{INTERNAL_PREFIX}/orgs/{{org_id}}/entitlements", _READ_OR_GRANT),
)


def covered_paths() -> frozenset[tuple[str, str]]:
    """(method, path) pairs the pilot must expose as tools."""
    return frozenset((e.method.upper(), e.path) for e in PILOT_SCOPE)


def exempted_paths() -> frozenset[tuple[str, str]]:
    """(method, path) pairs deliberately deferred, each with a reason."""
    return frozenset((e.method.upper(), e.path) for e in EXEMPTIONS)


def tool_names() -> frozenset[str]:
    return frozenset(e.tool_name for e in PILOT_SCOPE)
