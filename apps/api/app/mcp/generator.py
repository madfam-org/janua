"""Turn an OpenAPI schema into typed, purpose-named MCP tool specs.

This is the extractable core of the pilot. It knows nothing about janua beyond the
OpenAPI document it is handed and a small per-service ``ToolOverride`` table; give it
another service's OpenAPI + overrides and it produces that service's tool specs the
same way. When the shared MCP-generator package the roadmap calls for is extracted,
THIS module moves out roughly unchanged and janua keeps only ``coverage.py`` (its
scope contract) and ``server.py`` (its auth/transport wiring). See the module README.

The mapping, endpoint -> tool:

* **name** -- not the HTTP verb+path, and not a generic ``call(method, path, body)``.
  A purpose name from the per-service override table (``janua_email_send``), so an
  agent reads intent, not routing. The roadmap is explicit that "an MCP tool is not a
  raw HTTP passthrough".
* **description** -- the endpoint's OpenAPI ``summary``/``description``, plus the
  override's purpose sentence, so the agent knows *when* to reach for it.
* **inputSchema** -- a JSON Schema built from the operation's path params, query
  params and (for writes) its requestBody schema, with ``$ref``s resolved against the
  document's ``components`` so the tool is self-describing. This is the "typed argument
  schema" the roadmap requires.
* **result shape** -- the operation's success (2xx) response schema, carried on the
  spec as ``output_schema`` so a caller can reason about what comes back.

The generator does not execute anything and holds no credentials; ``server.py`` binds
these specs to the janua HTTP API so the service's own auth gate runs unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JSONSchema = dict[str, Any]


@dataclass(frozen=True)
class ToolOverride:
    """Per-service, per-endpoint intent that the raw OpenAPI cannot carry.

    ``name`` is the purpose name; ``purpose`` is a one-sentence description prepended
    to the operation's own text; ``operator_gated`` marks a tool whose underlying
    action is irreversible/credentialed so the server layer can require an operator
    confirmation before it fires (none in the email pilot, but the field exists so the
    same generator serves the destructive endpoints in a later slice).
    """

    name: str
    purpose: str
    operator_gated: bool = False


@dataclass(frozen=True)
class ToolSpec:
    """A single generated MCP tool, transport-agnostic."""

    name: str
    description: str
    method: str
    path: str
    input_schema: JSONSchema
    output_schema: JSONSchema | None
    operator_gated: bool = False
    # The names of the input properties that are, respectively, path params, query
    # params and body fields -- so the transport layer knows how to place each
    # argument on the outgoing HTTP request.
    path_params: tuple[str, ...] = field(default_factory=tuple)
    query_params: tuple[str, ...] = field(default_factory=tuple)
    body_params: tuple[str, ...] = field(default_factory=tuple)
    body_is_whole: bool = False  # requestBody is a single object == the body


class GenerationError(RuntimeError):
    """Raised when the OpenAPI document cannot be mapped for a declared endpoint."""


def _resolve_ref(ref: str, root: dict[str, Any]) -> JSONSchema:
    if not ref.startswith("#/"):
        raise GenerationError(f"only local $refs are supported, got {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _inline_refs(schema: Any, root: dict[str, Any], _seen: frozenset[str] = frozenset()) -> Any:
    """Return a copy of ``schema`` with local ``$ref``s inlined.

    Cycles are broken by leaving an already-seen ``$ref`` in place (email schemas are
    acyclic, but the guard is defensive so the generator stays reusable).
    """
    if isinstance(schema, dict):
        if "$ref" in schema and isinstance(schema["$ref"], str):
            ref = schema["$ref"]
            if ref in _seen:
                return {"$ref": ref}
            resolved = _resolve_ref(ref, root)
            return _inline_refs(resolved, root, _seen | {ref})
        return {k: _inline_refs(v, root, _seen) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_inline_refs(v, root, _seen) for v in schema]
    return schema


def _success_response_schema(operation: dict[str, Any], root: dict[str, Any]) -> JSONSchema | None:
    responses = operation.get("responses", {})
    for code in ("200", "201", "202", "2XX", "default"):
        entry = responses.get(code)
        if not entry:
            continue
        content = entry.get("content", {})
        media = content.get("application/json")
        if media and "schema" in media:
            return _inline_refs(media["schema"], root)
    return None


def _request_body_schema(operation: dict[str, Any], root: dict[str, Any]) -> JSONSchema | None:
    body = operation.get("requestBody")
    if not body:
        return None
    media = body.get("content", {}).get("application/json")
    if not media or "schema" not in media:
        return None
    return _inline_refs(media["schema"], root)


def _build_tool(
    method: str,
    path: str,
    operation: dict[str, Any],
    override: ToolOverride,
    root: dict[str, Any],
) -> ToolSpec:
    properties: JSONSchema = {}
    required: list[str] = []
    path_params: list[str] = []
    query_params: list[str] = []

    for param in operation.get("parameters", []):
        param = _inline_refs(param, root)
        loc = param.get("in")
        name = param.get("name")
        if loc not in ("path", "query") or not name:
            continue
        prop = dict(param.get("schema", {"type": "string"}))
        if param.get("description"):
            prop.setdefault("description", param["description"])
        properties[name] = prop
        if param.get("required") or loc == "path":
            required.append(name)
        (path_params if loc == "path" else query_params).append(name)

    body_params: list[str] = []
    body_is_whole = False
    body_schema = _request_body_schema(operation, root)
    if body_schema is not None:
        if body_schema.get("type") == "object" and "properties" in body_schema:
            for prop_name, prop_schema in body_schema["properties"].items():
                properties[prop_name] = prop_schema
                body_params.append(prop_name)
            for req in body_schema.get("required", []):
                if req not in required:
                    required.append(req)
        else:
            # A non-object body (rare): expose it under a single ``body`` argument.
            properties["body"] = body_schema
            body_params.append("body")
            body_is_whole = True
            required.append("body")

    input_schema: JSONSchema = {
        "type": "object",
        "properties": properties,
        "required": sorted(set(required)),
        "additionalProperties": False,
    }

    op_text = operation.get("summary") or operation.get("description") or ""
    description = override.purpose if not op_text else f"{override.purpose} ({op_text})"
    if override.operator_gated:
        description += (
            " OPERATOR-GATED: this action is irreversible/credentialed; the server "
            "requires an explicit operator confirmation before it fires."
        )

    return ToolSpec(
        name=override.name,
        description=description,
        method=method.upper(),
        path=path,
        input_schema=input_schema,
        output_schema=_success_response_schema(operation, root),
        operator_gated=override.operator_gated,
        path_params=tuple(path_params),
        query_params=tuple(query_params),
        body_params=tuple(body_params),
        body_is_whole=body_is_whole,
    )


def generate_tools(
    openapi: dict[str, Any],
    overrides: dict[tuple[str, str], ToolOverride],
) -> list[ToolSpec]:
    """Build ToolSpecs for every (METHOD, path) present in ``overrides``.

    ``overrides`` is keyed by ``(METHOD, path)`` with METHOD upper-cased. Every key
    MUST resolve to an operation in the document; a missing one is a ``GenerationError``
    -- that is the generator half of the drift guard (a declared endpoint the schema no
    longer has). The coverage guard test supplies the other half (a schema endpoint no
    tool declares).
    """
    paths = openapi.get("paths", {})
    specs: list[ToolSpec] = []
    for (method, path), override in sorted(overrides.items()):
        path_item = paths.get(path)
        if path_item is None:
            raise GenerationError(f"OpenAPI has no path {path!r} for tool {override.name!r}")
        operation = path_item.get(method.lower())
        if operation is None:
            raise GenerationError(
                f"OpenAPI path {path!r} has no {method} operation for tool {override.name!r}"
            )
        specs.append(_build_tool(method, path, operation, override, openapi))
    return specs
