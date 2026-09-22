"""The runnable janua MCP server for the transactional-email pilot slice.

It ties the three other modules together:

* ``coverage.PILOT_SCOPE`` says which endpoints become tools and their purpose names.
* ``generator.generate_tools`` reads the committed OpenAPI snapshot (the source of
  truth) and produces typed ``ToolSpec``s -- one per endpoint, with an OpenAPI-derived
  ``inputSchema`` and the endpoint's success-response schema as its result shape.
* ``http_client.JanuaHttpClient`` calls janua's own HTTP API with the same
  ``X-Internal-API-Key`` gate, so the service's auth runs unchanged (no back door).

The MCP surface is served through the SDK's high-level ``MCPServer``, whose
``list_tools``/``call_tool`` we override so the schemas come from OpenAPI rather than
from Python function signatures. Run it over stdio:

    JANUA_API_BASE_URL=https://auth.madfam.io \\
    JANUA_INTERNAL_API_KEY=... \\
    python -m app.mcp

The overrides table is the ONLY janua-specific knowledge here; everything else is the
generic generator, which is why the generator is extractable to a shared package later
(roadmap follow-up). See app/mcp/README.md.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.server import MCPTool
from mcp.types import CallToolResult, TextContent

from . import coverage
from .generator import ToolOverride, ToolSpec, generate_tools
from .http_client import HttpConfig, JanuaHttpClient

SNAPSHOT_PATH = pathlib.Path(__file__).with_name("openapi_snapshot.json")

# The per-service override table: purpose names + one-line intents for the pilot
# endpoints. Keyed (METHOD, path), matching coverage.PILOT_SCOPE. This is the single
# place janua's intent is injected into the generic generator.
OVERRIDES: dict[tuple[str, str], ToolOverride] = {
    (e.method.upper(), e.path): ToolOverride(name=e.tool_name, purpose=e.summary)
    for e in coverage.PILOT_SCOPE
}


def load_snapshot(path: pathlib.Path = SNAPSHOT_PATH) -> dict[str, Any]:
    """Load the committed OpenAPI subset the tools are generated from."""
    return json.loads(path.read_text(encoding="utf-8"))


def build_specs(openapi: dict[str, Any] | None = None) -> list[ToolSpec]:
    """Generate the pilot's ToolSpecs from the OpenAPI snapshot."""
    return generate_tools(openapi or load_snapshot(), OVERRIDES)


def _place_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
    """Split validated tool arguments into path/query/body for the HTTP request."""
    path = spec.path
    for name in spec.path_params:
        if name in arguments and arguments[name] is not None:
            path = path.replace("{" + name + "}", str(arguments[name]))
    query = {name: arguments[name] for name in spec.query_params if name in arguments}
    body: dict[str, Any] | None
    if spec.body_is_whole:
        body = arguments.get("body")
    elif spec.body_params:
        body = {name: arguments[name] for name in spec.body_params if name in arguments}
    else:
        body = None
    return path, query, body


class JanuaMCPServer(MCPServer):
    """An MCPServer whose tools are the generated ToolSpecs, not decorated functions."""

    def __init__(self, specs: list[ToolSpec], client: JanuaHttpClient) -> None:
        super().__init__(name="janua-mcp")
        self._specs = {spec.name: spec for spec in specs}
        self._client = client

    async def list_tools(self) -> list[MCPTool]:  # type: ignore[override]
        tools: list[MCPTool] = []
        for spec in self._specs.values():
            tools.append(
                MCPTool(
                    name=spec.name,
                    description=spec.description,
                    input_schema=spec.input_schema,
                    output_schema=spec.output_schema,
                )
            )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> CallToolResult:  # type: ignore[override]
        spec = self._specs.get(name)
        if spec is None:
            return CallToolResult(
                content=[TextContent(type="text", text=f"unknown tool: {name}")], is_error=True
            )
        if spec.operator_gated:
            # No operator-gated tools ship in the email pilot; this is the enforcement
            # point for the follow-on destructive slice. Fail closed if one appears
            # without a confirmation path wired in.
            return CallToolResult(
                content=[TextContent(type="text", text=f"tool {name} is operator-gated and not enabled")],
                is_error=True,
            )
        path, query, body = _place_arguments(spec, arguments)
        response = await self._client.request(spec.method, path, query=query, json_body=body)
        try:
            payload = response.json()
            text = json.dumps(payload, ensure_ascii=False)
        except ValueError:
            payload = None
            text = response.text
        # A non-2xx from janua (e.g. 401 wrong key, 400 bad template) is surfaced as a
        # tool error carrying janua's own body -- the gate's verdict reaches the agent
        # verbatim, never swallowed. Note /send and /send-template return 200 with
        # EmailResponse.success == false on a Resend rejection, so also treat that as an
        # error so an agent learns a send did not land.
        is_error = response.is_error or (isinstance(payload, dict) and payload.get("success") is False)
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            structured_content=payload if isinstance(payload, dict) else None,
            is_error=is_error,
        )


def create_server() -> JanuaMCPServer:
    """Build the server from configured env + the committed snapshot. Fails closed."""
    config = HttpConfig.from_env()
    client = JanuaHttpClient(config)
    specs = build_specs()
    return JanuaMCPServer(specs, client)


def main() -> None:
    server = create_server()
    server.run("stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
