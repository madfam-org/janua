"""MAP attempt metadata is mandatory; it grants no provider or human authority."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import verify_internal_api_key
from app.main import app


@pytest.mark.parametrize("endpoint", ["send", "send-template"])
@pytest.mark.parametrize("upstream", [None, "", "not-a-uuid"])
async def test_map_rejects_missing_or_malformed_attempt_before_transport(
    monkeypatch, endpoint, upstream
):
    provider = AsyncMock()
    monkeypatch.setattr("app.routers.v1.email.ResendService", provider)
    app.dependency_overrides[verify_internal_api_key] = lambda: True
    body = {"to": ["synthetic-person@example.com"], "source_app": "crea-map"}
    if endpoint == "send":
        body.update(subject="Synthetic", text="Synthetic")
    else:
        body.update(template="map/pago-confirmado", variables={"periodo": "octubre de 2026"})
    headers = {} if upstream is None else {"X-MAP-Mail-Audit-ID": upstream}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/internal/email/" + endpoint, json=body, headers=headers
            )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "map_mail_audit_id_required"
        provider.assert_not_called()
    finally:
        app.dependency_overrides.pop(verify_internal_api_key, None)
