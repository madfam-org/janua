"""
Schemas for internal service-to-service API endpoints.
Used by hub services (Dhanam, etc.) to sync state with Janua.
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.services.email_i18n import SpanishFormality


class TierSyncRequest(BaseModel):
    """Request to sync an organization's subscription tier from Dhanam."""

    tier: Literal["free_tier", "pro_tier", "scale_tier", "enterprise_tier"]
    source: str = "dhanam"
    idempotency_key: str


class TierSyncResponse(BaseModel):
    """Response after syncing an organization's subscription tier."""

    status: str
    previous_tier: Optional[str] = None
    new_tier: str


def _validate_org_alias(model):
    """Enforce "exactly one of organization_id / tenant_id" on a request model.

    `tenant_id` is the DEPRECATED spelling, kept accepted so the current
    crea-map caller (which sends `tenant_id` only) keeps working unchanged
    across this deploy; it will move to `organization_id` in a follow-up.

    Both-with-the-SAME-value is allowed and harmless — a caller mid-migration
    may legitimately send both. Both with DIFFERENT values is rejected: there
    is no defensible way to pick one, and silently preferring either could
    provision a person into the wrong organization.
    """
    org, tenant = model.organization_id, model.tenant_id
    if org is None and tenant is None:
        raise ValueError("one of organization_id (preferred) or tenant_id is required")
    if org is not None and tenant is not None and org != tenant:
        raise ValueError(
            "organization_id and tenant_id name the same organization; "
            "they must match (send organization_id alone)"
        )
    return model


class ProvisionUserRequest(BaseModel):
    """Request to ensure a janua user exists for a sibling app's roster member."""

    email: EmailStr
    first_name: str = Field(min_length=1, max_length=255)
    last_name: Optional[str] = Field(default=None, max_length=255)
    # The ORGANIZATION this person belongs to. Exactly one of `organization_id`
    # (preferred) or `tenant_id` (deprecated alias) must be sent; both name the
    # same `organizations.id`, and `organization_id` is authoritative when both
    # appear with the same value. Read it through `org_id`, never directly.
    #
    # The rename is the point: this field used to do TWO jobs — name the
    # organization for the membership AND select the identity pool — and
    # conflating them is what put 21 CTM staff accounts in a tenant pool, where
    # the magic-link lookup could not find them (see the outage in this PR).
    # Which pool the identity lives in is now `identity_pool`'s job alone.
    organization_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    # WHICH EMAIL-UNIQUENESS POOL the identity itself lives in.
    #
    #   "platform" (DEFAULT) — `users.tenant_id` is NULL. The person is org
    #       STAFF: a colleague who signs in to MADFAM products. They belong to
    #       the organization through their `organization_members` row, which
    #       this endpoint still ensures, NOT through a column on `users`. This
    #       is the correct shape for every caller today (crea-map's «Alta de
    #       integrante» included), and it is what keeps the bare-email entry
    #       points — magic link, password reset — able to find them.
    #
    #   "tenant" — `users.tenant_id` is set to the organization. Reserved for
    #       real BaaS end-user provisioning (Phase 1): a client's own end users,
    #       who live in that client's isolated pool and are never expected to
    #       resolve through MADFAM's platform entry points.
    #
    # Defaulting to "platform" deliberately changes the behaviour of existing
    # callers that omit the field, because their existing behaviour is the bug.
    identity_pool: Literal["platform", "tenant"] = "platform"
    # Mark the provisioned identity as a technical/service account rather than
    # a person. Defaults to False: a roster app that says nothing is
    # provisioning a colleague, which is the overwhelmingly common case and
    # today's only behaviour.
    #
    # Honoured ONLY on creation. An existing row is returned untouched by this
    # endpoint (see the handler docstring: this is provisioning, not
    # synchronization), and that rule holds for this field too — flipping a
    # live identity between "person" and "service" is an operator decision with
    # roster- and signature-visible consequences, not something a roster app
    # should be able to do as a side effect of a retry.
    is_service_account: bool = False
    # Organization role for the membership this call ensures in `tenant_id`'s
    # organization. Optional; defaults to the least-privileged role that still
    # produces org claims.
    #
    # Constrained to the org-membership vocabulary (`OrganizationRole` in
    # models/__init__.py:574-578) rather than a free string: `role` lands in the
    # `madfam_org_roles` token claim, so an unvalidated value would let a roster
    # app mint an arbitrary authorization string that a resource server might
    # honour. `owner` is deliberately NOT offered — organization ownership is an
    # operator decision (`Organization.owner_id`), not something a roster
    # «Alta de integrante» should be able to grant over the internal API.
    org_role: Literal["admin", "member", "viewer"] = "member"

    @model_validator(mode="after")
    def _exactly_one_org_field(self) -> "ProvisionUserRequest":
        return _validate_org_alias(self)

    @property
    def org_id(self) -> UUID:
        """The organization, from whichever of the two spellings was sent."""
        return self.organization_id or self.tenant_id  # type: ignore[return-value]


class ProvisionUserResponse(BaseModel):
    """Result of a provisioning call. `created` distinguishes 201 from 200."""

    id: str
    email: str
    status: str
    created: bool
    created_at: datetime
    # Echoes the identity's stored flag — for a pre-existing row this is the
    # STORED value, which may differ from what the caller requested, so a
    # caller can detect the "already exists, and it is/is not a service
    # account" case without a second read.
    is_service_account: bool = False
    # The role of the ACTIVE organization membership this identity holds in
    # `tenant_id`'s organization, or None when it holds none (which is the case
    # for a legacy row provisioned before memberships were written, and for any
    # future caller that provisions into no organization).
    #
    # Reported so a roster app can verify — without a second read and without
    # decoding a token — that the person will actually carry `org_id`. That is
    # the whole point of this endpoint's contract with symbiosis-hcm: no active
    # membership means no `org_id` claim means 403 at `/employees/me/`.
    org_role: Optional[str] = None


class UserLifecycleRequest(BaseModel):
    """Request to suspend or reactivate a roster member's janua access."""

    email: EmailStr
    # Same alias rule as ProvisionUserRequest: exactly one of these, both
    # naming the same `organizations.id`. Read through `org_id`.
    #
    # There is deliberately NO `identity_pool` here. A lifecycle call names a
    # person who already exists, and the handler resolves them across pools
    # (platform first, then the cross-pool resolver) so it keeps working for
    # identities provisioned under the OLD tenant-pooled default as well as
    # new platform-pooled ones. Making the caller declare the pool would
    # reintroduce exactly the guessing this change removes.
    organization_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None

    @model_validator(mode="after")
    def _exactly_one_org_field(self) -> "UserLifecycleRequest":
        return _validate_org_alias(self)

    @property
    def org_id(self) -> UUID:
        """The organization, from whichever of the two spellings was sent."""
        return self.organization_id or self.tenant_id  # type: ignore[return-value]


class UserLifecycleResponse(BaseModel):
    """Result of a lifecycle call. `changed` is False when already in state."""

    id: str
    email: str
    status: str
    changed: bool


# The `source_app` shape: a short lowercase product slug (`nauta`, `phynd-crm`).
# Validated for SHAPE only, like every other product name janua records — janua
# holds no table of products, and a new one must not need a janua deploy.
SOURCE_APP_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,63}$"


class SpanishFormalityWriteRequest(BaseModel):
    """A product relaying the `tú`/`usted` answer a person gave INSIDE it.

    Address the person by exactly one of:

    * ``user_id`` — their janua user id (the ``sub`` of their janua token). This
      is how a product that signs people in through janua knows them.
      ``organization_id`` is optional here; when sent, the person must hold a
      membership in that organization or the call is a 404.
    * ``email`` + ``organization_id`` — for a product that knows the person only
      by address. Resolved the way the lifecycle endpoints resolve it (platform
      pool, then the organization's pool) and scoped to people who hold a
      membership in that organization, so naming an organization never reaches
      somebody else's person.

    ``spanish_formality`` is REQUIRED and must be exactly ``"tu"`` or
    ``"usted"``; ``null`` is refused (422). NULL on the row means "never asked",
    and a relay cannot put it back.
    """

    user_id: Optional[UUID] = None
    email: Optional[EmailStr] = None
    organization_id: Optional[UUID] = None
    spanish_formality: SpanishFormality
    # Which product heard the answer. Recorded on the audit row: the internal key
    # is shared by every sibling app, so this is the only place "which product"
    # is written down.
    source_app: str = Field(pattern=SOURCE_APP_PATTERN)

    @model_validator(mode="after")
    def _exactly_one_address(self) -> "SpanishFormalityWriteRequest":
        if (self.user_id is None) == (self.email is None):
            raise ValueError("send exactly one of user_id or email")
        if self.email is not None and self.organization_id is None:
            raise ValueError(
                "organization_id is required with email: an address is looked up "
                "within one organization's people"
            )
        return self


class SpanishFormalityWriteResponse(BaseModel):
    """Result of a relay. `changed` is False when that register was already stored."""

    id: str
    spanish_formality: SpanishFormality
    # What was stored before this call; None when the person had never been asked.
    previous_spanish_formality: Optional[str] = None
    changed: bool
