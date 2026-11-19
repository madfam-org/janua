"""The application-role names a client platform granted on 2026-11-18/19.

Through the internal app-roles routes (``POST /api/v1/internal/app-roles/grant``
and ``/revoke``) a client platform granted and revoked four new role names in
two reserved product namespaces. Janua holds no vocabulary of role names, so
nothing else in the suite names them; this pins that their shape is the one the
rest of Janua assumes:

- the grant schema accepts each ``(app, role)`` pair and the claim value is
  exactly ``<app>:<role>``, with one colon;
- the claim value has the application-role shape and its namespace is a
  reserved product namespace, so the same string as an OAuth client SCOPE is a
  platform-admin value (``is_reserved_scope``) and never one an organization
  admin can put on a client;
- none of them is tenant-bound, and none is ``<app>:admin``: an ``erp-admin``
  or ``space-owner`` grant does not make anyone the delegated administrator of
  that app's roles (``organization_app_roles.APP_ADMIN_ROLE``).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core import reserved_oauth_boundaries as reserved
from app.models.app_role import APP_ROLE_SEPARATOR, format_app_role
from app.routers.v1.organization_app_roles import APP_ADMIN_ROLE
from app.schemas.app_role import AppRoleGrantRequest

GRANTED_2026_11 = [
    ("nauta", "erp-admin"),
    ("nauta", "erp-viewer"),
    ("dhanam", "space-owner"),
    ("dhanam", "space-viewer"),
]


@pytest.mark.parametrize(("app", "role"), GRANTED_2026_11)
def test_grant_schema_accepts_the_pair_and_the_claim_has_one_colon(app, role):
    request = AppRoleGrantRequest(organization_id=uuid4(), user_id=uuid4(), app=app, role=role)
    claim = format_app_role(request.app, request.role)
    assert claim == f"{app}:{role}"
    assert claim.count(APP_ROLE_SEPARATOR) == 1


@pytest.mark.parametrize(("app", "role"), GRANTED_2026_11)
def test_claim_is_in_a_reserved_product_namespace(app, role):
    claim = format_app_role(app, role)
    assert reserved.APP_ROLE_SCOPE_SHAPE.match(claim), claim
    assert app in reserved.RESERVED_SCOPE_NAMESPACES
    assert claim not in reserved.TENANT_BOUND_MACHINE_SCOPES
    assert reserved.is_reserved_scope(claim), claim


@pytest.mark.parametrize(("app", "role"), GRANTED_2026_11)
def test_none_of_them_is_the_delegated_admin_role(app, role):
    assert role != APP_ADMIN_ROLE
    assert not format_app_role(app, role).endswith(reserved.RESERVED_SCOPE_SUFFIXES)


@pytest.mark.parametrize("bad", ["nauta:erp-admin", "erp admin", " ", ""])
def test_a_composite_or_blank_role_is_refused(bad):
    """The colon stays the only separator: a caller cannot pass the whole claim
    as the role and fabricate ``nauta:nauta:erp-admin``."""
    with pytest.raises(ValueError):
        AppRoleGrantRequest(organization_id=uuid4(), user_id=uuid4(), app="nauta", role=bad)
