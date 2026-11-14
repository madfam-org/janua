"""Bounded source lookup contract; native storage/operator proof is separate."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.dialects.postgresql import dialect

from app.auth.session_bridge_state import InvalidBridgeState
from app.core.reserved_oauth_boundaries import SILENT_AUTH_SCOPE
from app.routers.v1 import session_bridge as bridge

URI = "https://map.example.test/F_901%"


def client(**changes):
    return SimpleNamespace(
        client_id="jnc_F-901",
        name="F-901",
        is_active=True,
        is_confidential=True,
        allowed_scopes=[SILENT_AUTH_SCOPE],
        grant_types=["authorization_code"],
        redirect_uris=[URI],
        **changes,
    )


def database(rows):
    result = Mock()
    result.all.return_value = rows
    return SimpleNamespace(execute=AsyncMock(return_value=result))


def test_query_uses_jsonb_array_containment_and_only_extracted_text_like():
    query = bridge._source_query(URI)
    compiled = query.compile(dialect=dialect())
    sql = str(compiled)
    assert "@>" in sql and "#>>" in sql and "ESCAPE" in sql
    assert "AS JSONB) LIKE" not in sql
    assert query._limit_clause.value == 3
    assert any(
        isinstance(value, str) and "/_" in value and "/%" in value
        for value in compiled.params.values()
    )
    assert "translate(" in sql  # ASCII name policy prefilter, no locale-only broadened trust.


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", [[URI], json.dumps(["https://map.example.test/F-902", URI])])
async def test_exact_top_level_member_is_reloaded_and_trusted(monkeypatch, stored):
    db = database([("jnc_F-901", stored)])
    lookup = AsyncMock(return_value=client())
    monkeypatch.setattr(bridge, "_get_oauth_client", lookup)
    result = await bridge._source_client(URI, db)
    assert result.client_id == "jnc_F-901"
    lookup.assert_awaited_once_with("jnc_F-901", db)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rows",
    [
        [],
        [("jnc_F-901", [URI + "/F-903"])],
        [("jnc_F-901", [URI.replace("_", "X").replace("%", "Y")])],
        [("jnc_F-901", {"F-904": URI})],
        [("jnc_F-901", json.dumps({"F-904": URI}))],
        [("jnc_F-901", "not-json")],
        [("jnc_F-901", [URI, 1])],
        [("jnc_F-901", [URI]), ("jnc_F-902", [URI])],
        [("jnc_F-901", [URI])] * 3,
    ],
)
async def test_absence_near_match_malformed_duplicate_or_overflow_never_selects(monkeypatch, rows):
    lookup = AsyncMock()
    monkeypatch.setattr(bridge, "_get_oauth_client", lookup)
    with pytest.raises(InvalidBridgeState):
        await bridge._source_client(URI, database(rows))
    lookup.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["disabled", "public", "untrusted", "uri", "grant"])
async def test_policy_and_uri_are_rechecked_on_unique_source_reload(monkeypatch, change):
    loaded = client()
    if change == "disabled":
        loaded.is_active = False
    elif change == "public":
        loaded.is_confidential = False
    elif change == "untrusted":
        loaded.allowed_scopes = ["openid"]
    elif change == "uri":
        loaded.redirect_uris = [URI + "/F-903"]
    else:
        loaded.grant_types = ["client_credentials"]
    monkeypatch.setattr(bridge, "_get_oauth_client", AsyncMock(return_value=loaded))
    with pytest.raises(InvalidBridgeState):
        await bridge._source_client(URI, database([("jnc_F-901", [URI])]))
