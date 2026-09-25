"""Schemas for the application-roles APIs (internal and delegated).

Design rules these types enforce:

* ``app`` and ``role`` are OPAQUE STRINGS. There is no enum of known apps and no
  vocabulary of role names, exactly as there is none for capability-link scopes.
  The resource server owns its own role names; janua records WHO was granted
  WHAT, by whom, and when. Adding an enum here would mean every new HCM role
  needed a janua deploy.
* Janua still validates SHAPE, because a malformed grant is a caller bug that
  should not become a live authorization row: no blank strings, no whitespace,
  and no separator inside a component. That last one matters — the claim value
  is ``f"{app}:{role}"``, so an ``app`` of ``"hcm:hr"`` would emit
  ``"hcm:hr:x"`` and could FABRICATE a role string the resource server matches.
  This is the same failure mode `capability_link.scopes` avoids by being JSONB
  rather than a delimited string.
* The org is named by ``organization_id`` and the person by ``user_id`` — the
  caller states both, and the handler resolves them to the ONE membership the
  grant hangs off. There is no shape in which a caller grants a role without
  naming the organization it applies in.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.app_role import APP_ROLE_SEPARATOR, MAX_APP_LENGTH, MAX_ROLE_LENGTH


def _validate_component(value: str, *, field: str, max_length: int) -> str:
    """Shape-check one half of an application role. Never a meaning check."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    if len(cleaned) > max_length:
        raise ValueError(f"{field} exceeds {max_length} characters")
    if APP_ROLE_SEPARATOR in cleaned:
        # The emitted claim is f"{app}:{role}". A separator inside a component
        # would let a caller synthesize a role string the resource server did
        # not intend to be grantable — authority fabricated by punctuation.
        raise ValueError(f"{field} must not contain {APP_ROLE_SEPARATOR!r}")
    if any(c.isspace() for c in cleaned):
        raise ValueError(f"{field} must not contain whitespace")
    return cleaned


class AppRoleGrantRequest(BaseModel):
    """Grant one application role to one person inside one organization."""

    # REQUIRED and never defaulted, for the same reason as on every other
    # internal schema: it selects the isolation boundary. A defaulted org would
    # let a caller that forgot the field grant HR authority in the WRONG tenant.
    organization_id: UUID
    user_id: UUID

    app: str = Field(min_length=1, max_length=MAX_APP_LENGTH)
    role: str = Field(min_length=1, max_length=MAX_ROLE_LENGTH)

    @field_validator("app")
    @classmethod
    def _validate_app(cls, value: str) -> str:
        return _validate_component(value, field="app", max_length=MAX_APP_LENGTH)

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        return _validate_component(value, field="role", max_length=MAX_ROLE_LENGTH)


class AppRoleRevokeRequest(AppRoleGrantRequest):
    """Retire one application role. Same addressing as the grant."""


class AppRoleGrantResponse(BaseModel):
    """Result of a grant or revoke.

    ``changed`` distinguishes "this call did it" from "it was already so", the
    same idempotency signal ``internal_users.py`` reports on suspend/reactivate.
    ``claim_value`` echoes the exact string that will appear in the token's
    ``roles`` claim, so a caller can assert on it without re-deriving the format.
    """

    id: Optional[str] = None
    organization_id: str
    user_id: str
    app: str
    role: str
    claim_value: str
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    changed: bool


class AppRoleEntry(BaseModel):
    """One grant in a listing."""

    id: str
    app: str
    role: str
    claim_value: str
    granted_by: Optional[str] = None
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None


class AppRoleListResponse(BaseModel):
    """Every grant for one membership.

    ``claim_values`` is the resolved live set — exactly what the person's next
    token will carry under ``roles`` — so an operator can answer "why can they
    not see HR?" without decoding a JWT. ``grants`` carries the history,
    including revoked rows, because who took an authority away and when is the
    question this table exists to answer.
    """

    organization_id: str
    user_id: str
    claim_values: List[str]
    grants: List[AppRoleEntry]


# ---------------------------------------------------------------------------
# Delegated administration (routers/v1/organization_app_roles.py)
#
# The same grants, managed by a person instead of an operator: an active member
# holding a live ``<app>:admin`` grant in an organization administers roles OF
# THAT APP in THAT organization. The organization and the app come from the
# PATH, never the body, so there is no body shape that names a second tenant or
# a second app.
# ---------------------------------------------------------------------------


def validate_app_slug(value: str) -> str:
    """Shape-check an ``app`` taken from a URL path (same rules as the body)."""
    return _validate_component(value, field="app", max_length=MAX_APP_LENGTH)


class DelegatedAppRoleGrantRequest(BaseModel):
    """Grant ``<app>:<role>`` to one member, named by ``user_id`` OR ``email``.

    ``email`` is resolved ONLY among the ACTIVE members of the path's
    organization, never against the global user table: an app admin can reach
    their own colleagues and nobody else, and an address that is not a colleague
    answers exactly like a user id that is not one.
    """

    user_id: Optional[UUID] = None
    email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    role: str = Field(min_length=1, max_length=MAX_ROLE_LENGTH)

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        return _validate_component(value, field="role", max_length=MAX_ROLE_LENGTH)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip().lower()
        if "@" not in cleaned or any(c.isspace() for c in cleaned):
            raise ValueError("email is not an email address")
        return cleaned

    @model_validator(mode="after")
    def _exactly_one_target(self) -> DelegatedAppRoleGrantRequest:
        if (self.user_id is None) == (self.email is None):
            raise ValueError("name the member by exactly one of user_id or email")
        return self


class DelegatedAppRoleRevokeRequest(BaseModel):
    """Retire ``<app>:<role>`` from one member, named by ``user_id``."""

    user_id: UUID
    role: str = Field(min_length=1, max_length=MAX_ROLE_LENGTH)

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        return _validate_component(value, field="role", max_length=MAX_ROLE_LENGTH)


class AppRoleMember(BaseModel):
    """An active member of the organization, as an app admin may see them."""

    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None


class DelegatedAppRoleGrant(BaseModel):
    """One LIVE grant of the app, with the member it belongs to."""

    id: str
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    role: str
    claim_value: str
    granted_by: Optional[str] = None
    granted_at: Optional[datetime] = None


class DelegatedAppRoleListResponse(BaseModel):
    """The live grants of ONE app in ONE organization.

    ``caller_roles`` are the caller's own live roles for this app (so a UI can
    tell "you are an admin of this app"), and ``members`` is the organization's
    active roster the caller may grant to.
    """

    organization_id: str
    app: str
    caller_user_id: str
    caller_roles: List[str]
    grants: List[DelegatedAppRoleGrant]
    members: List[AppRoleMember]


class MyAppRolesResponse(BaseModel):
    """The caller's own live application roles in one organization.

    ``administered_apps`` are the apps for which the caller holds a live
    ``<app>:admin`` grant here, i.e. the apps whose roles they may manage.
    """

    organization_id: str
    user_id: str
    claim_values: List[str]
    administered_apps: List[str]
