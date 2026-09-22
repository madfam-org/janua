"""The generator maps OpenAPI -> typed tools correctly, and auth rides through.

These tests use a tiny hand-built OpenAPI document (so they are independent of the
committed janua snapshot) plus the real snapshot for a couple of concrete assertions.
"""

from __future__ import annotations

import httpx
import pytest

from app.mcp.generator import GenerationError, ToolOverride, generate_tools
from app.mcp.http_client import HttpConfig, JanuaHttpClient, MCPConfigError
from app.mcp.server import JanuaMCPServer, build_specs

_MINI_OPENAPI = {
    "openapi": "3.1.0",
    "paths": {
        "/things/{thing_id}": {
            "get": {
                "summary": "Get a thing",
                "parameters": [
                    {"name": "thing_id", "in": "path", "required": True, "schema": {"type": "string"}},
                    {"name": "verbose", "in": "query", "required": False, "schema": {"type": "boolean"}},
                ],
                "responses": {
                    "200": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Thing"}}}
                    }
                },
            }
        },
        "/things": {
            "post": {
                "summary": "Create a thing",
                "requestBody": {
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/ThingCreate"}}
                    }
                },
                "responses": {
                    "201": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Thing"}}}
                    }
                },
            }
        },
    },
    "components": {
        "schemas": {
            "Thing": {"type": "object", "properties": {"id": {"type": "string"}}},
            "ThingCreate": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "size": {"type": "integer"}},
                "required": ["name"],
            },
        }
    },
}


def test_path_and_query_params_become_typed_inputs():
    overrides = {("GET", "/things/{thing_id}"): ToolOverride(name="get_thing", purpose="Read a thing.")}
    (spec,) = generate_tools(_MINI_OPENAPI, overrides)
    assert spec.name == "get_thing"
    assert spec.method == "GET"
    assert set(spec.input_schema["properties"]) == {"thing_id", "verbose"}
    assert spec.input_schema["required"] == ["thing_id"]  # path param is required
    assert spec.path_params == ("thing_id",)
    assert spec.query_params == ("verbose",)
    assert spec.input_schema["additionalProperties"] is False
    # Result shape is the inlined success response.
    assert spec.output_schema == {"type": "object", "properties": {"id": {"type": "string"}}}


def test_request_body_object_is_flattened_into_typed_inputs():
    overrides = {("POST", "/things"): ToolOverride(name="create_thing", purpose="Make a thing.")}
    (spec,) = generate_tools(_MINI_OPENAPI, overrides)
    assert set(spec.body_params) == {"name", "size"}
    assert spec.input_schema["properties"]["size"] == {"type": "integer"}
    assert "name" in spec.input_schema["required"]
    assert not spec.body_is_whole


def test_missing_endpoint_is_a_generation_error():
    overrides = {("GET", "/nope"): ToolOverride(name="nope", purpose="x")}
    with pytest.raises(GenerationError):
        generate_tools(_MINI_OPENAPI, overrides)


def test_missing_method_on_existing_path_is_a_generation_error():
    overrides = {("DELETE", "/things"): ToolOverride(name="del", purpose="x")}
    with pytest.raises(GenerationError):
        generate_tools(_MINI_OPENAPI, overrides)


def test_operator_gated_tool_is_refused_by_the_server():
    """A gated tool must never call the HTTP API; the pilot ships none, this pins it."""
    overrides = {("POST", "/things"): ToolOverride(name="danger", purpose="Boom.", operator_gated=True)}
    specs = generate_tools(_MINI_OPENAPI, overrides)
    called = {"n": 0}

    def handler(request):  # pragma: no cover - must not run
        called["n"] += 1
        return httpx.Response(200, json={})

    ac = httpx.AsyncClient(base_url="https://x", transport=httpx.MockTransport(handler))
    client = JanuaHttpClient(HttpConfig("https://x", "k"), client=ac)
    server = JanuaMCPServer(specs, client)

    import anyio

    result = anyio.run(server.call_tool, "danger", {"name": "n"})
    assert result.is_error
    assert called["n"] == 0  # the gate fired before any HTTP call


def test_config_fails_closed_without_key(monkeypatch):
    monkeypatch.delenv("JANUA_INTERNAL_API_KEY", raising=False)
    monkeypatch.setenv("JANUA_API_BASE_URL", "https://auth.test")
    with pytest.raises(MCPConfigError):
        HttpConfig.from_env()


def test_config_fails_closed_without_base_url(monkeypatch):
    monkeypatch.setenv("JANUA_INTERNAL_API_KEY", "k")
    monkeypatch.delenv("JANUA_API_BASE_URL", raising=False)
    with pytest.raises(MCPConfigError):
        HttpConfig.from_env()


def test_internal_api_key_is_attached_on_every_call():
    """The gate header is present and comes from config, never from tool args."""
    specs = build_specs()
    seen: list[dict[str, str]] = []

    def handler(request):
        seen.append(dict(request.headers))
        return httpx.Response(200, json={"success": True, "message_id": "m"})

    ac = httpx.AsyncClient(base_url="https://auth.test", transport=httpx.MockTransport(handler))
    client = JanuaHttpClient(HttpConfig("https://auth.test", "THE-KEY"), client=ac)
    server = JanuaMCPServer(specs, client)

    import anyio

    # An agent trying to smuggle its own key in as an argument must not win: the tool
    # schema has no such field, and the header is set from config regardless.
    anyio.run(
        server.call_tool,
        "janua_email_send",
        {"to": ["a@b.com"], "subject": "s", "source_app": "t", "X-Internal-API-Key": "attacker"},
    )
    assert seen, "no request was made"
    header = {k.lower(): v for k, v in seen[0].items()}["x-internal-api-key"]
    assert header == "THE-KEY"  # config value, not the argument


def test_send_email_tool_requires_source_app_subject_to():
    """The typed schema mirrors the API's own required fields (source_app, subject, to)."""
    specs = {s.name: s for s in build_specs()}
    send = specs["janua_email_send"]
    assert set(send.input_schema["required"]) >= {"source_app", "subject", "to"}
