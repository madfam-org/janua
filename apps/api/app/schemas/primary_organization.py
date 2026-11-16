"""Schemas for the internal primary-organization API.

A primary organization is the ONE organization a person's tokens speak for when
they hold several active memberships. It is chosen by an operator and recorded
in ``user_primary_organizations`` (migration 022); see
``routers/v1/internal_primary_organization.py`` for the rules the handlers hold
and ``services/org_claims_service.py`` for how it resolves into a token.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class PrimaryOrganizationSetRequest(BaseModel):
    """Make ``organization_id`` the primary organization of ``user_id``.

    Both are REQUIRED and never defaulted: the organization is the isolation
    boundary the person's tokens will speak for, and a defaulted one would let a
    caller that forgot the field pick a tenant by accident.
    """

    organization_id: UUID
    user_id: UUID


class PrimaryOrganizationClearRequest(BaseModel):
    """Remove the primary organization of ``user_id``."""

    user_id: UUID


class PrimaryOrganizationResponse(BaseModel):
    """The stored choice, and what the person's NEXT token resolves to.

    ``primary_organization_id`` is what is stored. ``active_membership`` says
    whether the person still holds an ACTIVE membership there — a stored value
    without one resolves to nothing. ``token_org_id`` and ``token_app_roles``
    are the resolver's own answer (the same function every minting seam calls),
    so an operator can see the effect — including ``tenant_id`` taking
    precedence — without decoding a JWT. ``changed`` is set on writes only: it
    says whether THIS call changed the stored value.
    """

    user_id: str
    primary_organization_id: Optional[str] = None
    active_membership: bool
    token_org_id: Optional[str] = None
    token_app_roles: List[str]
    changed: Optional[bool] = None
