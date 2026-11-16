"""Operator-set primary organization — one optional row per user.

Which organization a person's tokens speak for when they hold SEVERAL active
memberships and ``users.tenant_id`` names none of them. Without it the claims
resolver (``services/org_claims_service.py``) emits ``orgs`` alone for such a
person: no ``org_id``, no ``madfam_org_roles`` and no application roles.

Why a table and not a column on ``users``
-----------------------------------------
The ``User`` model is read on every login. A column there would make every
image that carries it fail ALL logins on a database where the migration has not
been applied — far too much coupling for an optional authorization hint. A
separate table is read in exactly one place, by the resolver, inside its own
guarded read that degrades to "no primary" on any failure (missing table
included), the same pattern as ``organization_member_app_roles`` (migration
016). So the code and the schema can ship in either order.

Why not ``users.tenant_id``
---------------------------
``tenant_id`` is the email-uniqueness pool the identity lives in (see
``routers/v1/internal_users.py``); pointing it at an organization once made
staff unreachable by magic link and password reset.

Shape
-----
``user_id`` is the primary key, so a person has at most one pointer. Both
foreign keys CASCADE: a deleted user takes their pointer with them, and a
deleted organization simply means no primary. ``organization_id`` is nullable
because clearing is an UPDATE to NULL, not a DELETE — the row keeps who last
wrote it and when, and the history of choices lives on the AuditLogger trail.

The pointer counts only while the user holds an ACTIVE membership in that
organization; the resolver checks that at every mint. Written only by an
operator through ``routers/v1/internal_primary_organization.py``.

Kept in its own module, outside ``app/models/__init__.py``, so the hot ``User``
model file is untouched. It is registered on ``Base.metadata`` wherever it is
imported — the claims service and the internal router both import it.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, String

from app.models import Base
from app.models.types import GUID as UUID

TABLE = "user_primary_organizations"
ORGANIZATION_INDEX = "ix_user_primary_organizations_organization_id"


class UserPrimaryOrganization(Base):
    """The one organization a multi-org person's tokens speak for."""

    __tablename__ = TABLE
    __table_args__ = (
        sa.PrimaryKeyConstraint("user_id", name="pk_user_primary_organizations"),
        # Serves the ON DELETE CASCADE from organizations and an operator's
        # "who has this org as primary?" — never the login path, which reads by
        # primary key.
        sa.Index(ORGANIZATION_INDEX, "organization_id"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    # Who last wrote the pointer (set or clear), and when.
    set_by = Column(String(255), nullable=False)
    set_at = Column(DateTime, nullable=False, default=datetime.utcnow)


__all__ = ["ORGANIZATION_INDEX", "TABLE", "UserPrimaryOrganization"]
