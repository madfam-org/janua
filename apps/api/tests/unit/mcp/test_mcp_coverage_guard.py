"""The MCP-vs-API drift guard for the janua email pilot.

This is the enforcement the roadmap (P1) names: "a guard test per service asserting
every declared endpoint has an MCP tool (or a written exemption)". It has three teeth:

1. **The committed OpenAPI snapshot has a tool for every email path.** Nothing under
   the pilot's email slice may exist in the schema without a generated MCP tool.

2. **Every declared pilot endpoint still exists in the snapshot.** A tool for an
   endpoint the API removed is caught by the generator (GenerationError); this test
   pins the reverse-safe direction too.

3. **Every internal endpoint (the full intended surface) is covered OR exempted.**
   This is the part that fails CI when a *new* internal endpoint appears: if someone
   adds ``POST /api/v1/internal/email/send-bulk`` (or any internal route) and neither
   adds it to ``PILOT_SCOPE`` nor writes an ``EXEMPTION`` for it, this test goes red.

Teeth (1) and (2) run offline against the committed snapshot -- no heavy app import, so
they run anywhere. Tooth (3) needs the full internal surface; it reads it from the live
app when importable and otherwise falls back to the snapshot's email paths (still
catching an un-tooled email endpoint). The CI job that installs the full API deps
exercises the live path; ``scripts/mcp_generate_openapi.py --check`` is the companion
guard that keeps the snapshot itself honest against the live app.
"""

from __future__ import annotations

import re

import pytest

from app.mcp import coverage
from app.mcp.server import build_specs, load_snapshot

# Normalize an OpenAPI path template so `/x/{a}` and `/x/{link_id}` compare by shape
# where the guard only cares about position, not the param's spelling. The coverage
# declarations use the live param names, so this is mostly identity; it exists so a
# rename of a path param in the schema does not silently defeat the exemption match.
_PARAM = re.compile(r"\{[^}]+\}")


def _norm(path: str) -> str:
    return _PARAM.sub("{}", path)


def _snapshot_email_ops() -> set[tuple[str, str]]:
    snap = load_snapshot()
    ops: set[tuple[str, str]] = set()
    for path, item in snap["paths"].items():
        for method, _op in item.items():
            if method.lower() in ("get", "post", "put", "delete", "patch"):
                ops.add((method.upper(), path))
    return ops


def test_every_email_endpoint_has_a_tool():
    """Tooth 1: every path in the snapshot maps to a generated tool."""
    snapshot_ops = _snapshot_email_ops()
    specs = build_specs()
    tool_ops = {(s.method, s.path) for s in specs}
    missing = snapshot_ops - tool_ops
    assert not missing, (
        f"email endpoints in the OpenAPI snapshot with no MCP tool: {sorted(missing)}. "
        "Add them to app/mcp/coverage.PILOT_SCOPE (with a purpose name) or the "
        "generator will not expose them."
    )


def test_every_declared_tool_maps_to_a_real_endpoint():
    """Tooth 2: no tool points at a snapshot path/method that is gone."""
    snapshot_ops = _snapshot_email_ops()
    specs = build_specs()
    stale = {(s.method, s.path) for s in specs} - snapshot_ops
    assert not stale, (
        f"MCP tools whose endpoint is not in the snapshot: {sorted(stale)}. "
        "Regenerate the snapshot or fix PILOT_SCOPE."
    )


def test_tool_names_are_unique_and_purposeful():
    specs = build_specs()
    names = [s.name for s in specs]
    assert len(names) == len(set(names)), f"duplicate tool names: {names}"
    for s in specs:
        # A purpose name, never a generic call(method,path,body) shape.
        assert s.name.startswith("janua_"), s.name
        assert "{" not in s.name and "/" not in s.name, s.name
        assert s.description and len(s.description) > 10, s.name


def _live_internal_ops() -> set[tuple[str, str]] | None:
    """Every (METHOD, path) under the internal prefix from the live app, or None."""
    try:
        import os

        os.environ.setdefault("INTERNAL_API_KEY", "test-openapi")
        from app.main import app
    except Exception:
        return None
    schema = app.openapi()
    ops: set[tuple[str, str]] = set()
    for path, item in schema.get("paths", {}).items():
        if not path.startswith(coverage.INTERNAL_PREFIX):
            continue
        for method, _op in item.items():
            if method.lower() in ("get", "post", "put", "delete", "patch"):
                ops.add((method.upper(), path))
    return ops


def test_full_internal_surface_is_covered_or_exempted():
    """Tooth 3: no internal endpoint is left undecided.

    The roadmap's "a future new endpoint without an MCP tool fails CI" property: any
    internal route that is neither in PILOT_SCOPE nor in EXEMPTIONS fails here.
    """
    live = _live_internal_ops()
    if live is None:
        # Offline fallback: still assert the email slice is fully covered.
        live = _snapshot_email_ops()

    covered = {(m, _norm(p)) for (m, p) in coverage.covered_paths()}
    exempted = {(m, _norm(p)) for (m, p) in coverage.exempted_paths()}
    decided = covered | exempted

    undecided = {(m, p) for (m, p) in live if (m, _norm(p)) not in decided}
    assert not undecided, (
        "internal janua endpoints with neither an MCP tool nor a written exemption: "
        f"{sorted(undecided)}. Add each to app/mcp/coverage.PILOT_SCOPE (expose it) or "
        "EXEMPTIONS (defer it, with a reason). This is the drift guard: a new endpoint "
        "cannot ship without a decision."
    )


def test_exemptions_do_not_overlap_scope():
    overlap = coverage.covered_paths() & coverage.exempted_paths()
    assert not overlap, f"paths both covered and exempted: {sorted(overlap)}"


def test_no_exemption_is_stale_against_the_live_surface():
    """An exemption for an endpoint the API no longer has is dead weight -- flag it.

    Only enforced when the live app is importable (CI full-deps job); skipped offline.
    """
    live = _live_internal_ops()
    if live is None:
        pytest.skip("live app not importable; snapshot fallback cannot see the full surface")
    live_norm = {(m, _norm(p)) for (m, p) in live}
    stale = {(m, p) for (m, p) in coverage.exempted_paths() if (m, _norm(p)) not in live_norm}
    assert not stale, (
        f"exemptions for endpoints not in the live API: {sorted(stale)}. Remove them from "
        "app/mcp/coverage.EXEMPTIONS."
    )
