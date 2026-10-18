"""POST /api/v1/auth/email/verify must use EmailVerification.verified_at.

The model has no boolean ``verified`` column. The route used to filter and set
one, so building the query raised AttributeError and every verification link
answered 500 (seen in production 2026-10-18). These tests run the route
function directly against a mocked session, so they need no database.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _session_returning(verification, user=None):
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = verification
    db.execute = AsyncMock(return_value=result)
    db.get = AsyncMock(return_value=user)
    db.commit = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_unknown_token_is_400_and_query_filters_on_verified_at():
    from app.routers.v1.auth import VerifyEmailRequest, verify_email

    db = _session_returning(None)
    with pytest.raises(HTTPException) as exc:
        await verify_email(VerifyEmailRequest(token="not-a-token"), db)

    assert exc.value.status_code == 400
    statement = db.execute.call_args.args[0]
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "verified_at IS NULL" in sql
    assert "email_verifications.verified " not in sql


@pytest.mark.asyncio
async def test_valid_token_marks_user_and_verification():
    from app.models import EmailVerification
    from app.routers.v1.auth import VerifyEmailRequest, verify_email

    verification = EmailVerification(
        user_id=None,
        email="someone@example.com",
        token="valid-token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    user = MagicMock()
    user.id = "00000000-0000-0000-0000-000000000001"
    user.email_verified = False
    db = _session_returning(verification, user)

    with patch("app.routers.v1.auth.log_activity", new=AsyncMock()), patch(
        "app.routers.v1.auth.log_audit_event", new=AsyncMock()
    ):
        response = await verify_email(VerifyEmailRequest(token="valid-token"), db)

    assert response == {"message": "Email successfully verified"}
    assert user.email_verified is True
    assert verification.verified_at is not None
    db.commit.assert_awaited_once()
