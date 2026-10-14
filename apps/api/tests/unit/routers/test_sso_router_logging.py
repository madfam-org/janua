"""SSO callbacks: the error-logging paths must log, not raise.

* `oidc_callback` logs an IdP error through a stdlib logger. It used to pass
  structlog-style keyword fields, which stdlib `Logger._log()` rejects with
  TypeError, so the IdP's error never reached the logs.

Real loggers, not patched.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

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
