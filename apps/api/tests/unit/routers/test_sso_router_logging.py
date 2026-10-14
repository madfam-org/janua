"""SSO callbacks: the error-logging paths must log, not raise.

* `oidc_callback` logs an IdP error through a stdlib logger. It used to pass
  structlog-style keyword fields, which stdlib `Logger._log()` rejects with
  TypeError, so the IdP's error never reached the logs.
* `saml_acs` bound `logger` locally (`logger = structlog.get_logger()`) deep in
  its `try`, which made `logger` local to the whole function: any failure
  before that line hit UnboundLocalError inside the `except` handler instead
  of the documented 500.

Real loggers, not patched.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

try:
    from app.routers.v1 import sso as sso_router
except Exception as exc:  # pragma: no cover - depends on the local xmlsec build
    # onelogin imports xmlsec at import time; on machines where lxml and xmlsec
    # link different libxml2 versions that import raises `xmlsec.Error`. CI
    # installs a matching libxmlsec1, so these tests run there.
    if type(exc).__module__ != "xmlsec":
        raise
    pytest.skip(f"xmlsec unavailable: {exc}", allow_module_level=True)

pytestmark = pytest.mark.asyncio

LOGGER_NAME = "app.routers.v1.sso"


async def test_oidc_idp_error_is_logged_with_fields_in_extra(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)

    with pytest.raises(HTTPException):
        await sso_router.oidc_callback(
            request=SimpleNamespace(),
            code="synthetic-code",
            state="synthetic-state",
            error="access_denied",
            error_description="synthetic description",
            db=MagicMock(),
            sso_service=MagicMock(),
        )

    (record,) = [r for r in caplog.records if r.getMessage() == "OIDC error"]
    assert record.error == "access_denied"
    assert record.description == "synthetic description"


async def test_saml_acs_failure_before_session_creation_returns_documented_500(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    request = SimpleNamespace(form=AsyncMock(return_value={}))  # no SAMLResponse

    with pytest.raises(HTTPException) as exc_info:
        await sso_router.saml_acs(request=request, db=MagicMock(), sso_service=MagicMock())

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "SSO authentication failed"
    assert any(r.getMessage().startswith("SAML ACS error") for r in caplog.records)
