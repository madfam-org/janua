"""Delete endpoints must await AsyncSession.delete.

`AsyncSession.delete` is a coroutine. Calling it without `await` schedules
nothing, so the following commit persists no deletion while the endpoint still
reports success. These tests call each endpoint with an AsyncMock session and
assert the delete was awaited, not merely called.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


def _result(row):
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    return result


async def test_delete_organization_awaits_delete():
    from app.routers.v1.organizations.core import delete_organization

    owner_id = uuid4()
    organization = SimpleNamespace(id=uuid4(), owner_id=owner_id)
    db = AsyncMock()

    await delete_organization(
        org_id=str(organization.id),
        organization=organization,
        current_user=SimpleNamespace(id=owner_id),
        db=db,
    )

    db.delete.assert_awaited_once_with(organization)
    db.commit.assert_awaited()


async def test_admin_delete_organization_awaits_delete():
    from app.routers.v1.admin import delete_organization_admin

    org = SimpleNamespace(id=uuid4())
    db = AsyncMock()
    db.execute.return_value = _result(org)

    await delete_organization_admin(
        org_id=str(org.id), current_user=SimpleNamespace(is_admin=True), db=db
    )

    db.delete.assert_awaited_once_with(org)
    db.commit.assert_awaited()


async def test_admin_permanent_user_delete_awaits_delete():
    from app.routers.v1.admin import delete_user_admin

    target = SimpleNamespace(id=uuid4(), email="target@janua.test")
    db = AsyncMock()
    db.execute.return_value = _result(target)

    await delete_user_admin(
        user_id=str(target.id),
        permanent=True,
        current_user=SimpleNamespace(id=uuid4(), is_admin=True),
        db=db,
    )

    db.delete.assert_awaited_once_with(target)
    db.commit.assert_awaited()


async def test_delete_passkey_awaits_delete():
    from app.routers.v1 import passkeys

    user = SimpleNamespace(id=uuid4(), password_hash="hash")
    passkey = SimpleNamespace(id=uuid4(), name="laptop")
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.return_value = _result(passkey)

    with patch.object(passkeys.AuthService, "verify_password", return_value=True):
        await passkeys.delete_passkey(
            passkey_id=str(passkey.id), password="pw", current_user=user, db=db
        )

    db.delete.assert_awaited_once_with(passkey)
    db.commit.assert_awaited()
