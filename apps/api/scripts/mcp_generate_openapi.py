#!/usr/bin/env python3
"""Dump the janua OpenAPI SUBSET the MCP pilot generates its tools from.

The live FastAPI app (``app.main:app``) is the source of truth. This script imports
it, calls ``app.openapi()``, and writes a *pruned* document containing only the paths
the pilot cares about -- the whole ``/api/v1/internal/email`` slice, plus the
components those operations reference -- to ``app/mcp/openapi_snapshot.json``.

Two jobs:

* **generate** (default): (re)write the snapshot. Run it after any change to the email
  router's request/response models so the committed snapshot tracks the API.
* **--check**: regenerate in memory and fail if it differs from the committed file.
  This is the CI drift guard between the API and the snapshot -- the same idiom as
  tlacuilo's ``check-schema`` and janua's ``PROD_ALEMBIC_STATE`` ledger check. Together
  with the coverage-guard unit test (tool set vs snapshot), a new email endpoint cannot
  reach production without either a tool or a written exemption.

Run from ``apps/api`` with the app importable:

    python scripts/mcp_generate_openapi.py            # write
    python scripts/mcp_generate_openapi.py --check     # verify (CI)
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

# The pilot slice: every path under this prefix is captured. Kept in sync with
# app/mcp/coverage.py (INTERNAL_PREFIX + the email router prefix).
SUBSET_PREFIX = "/api/v1/internal/email"

HERE = pathlib.Path(__file__).resolve()
API_ROOT = HERE.parents[1]  # apps/api
SNAPSHOT_PATH = API_ROOT / "app" / "mcp" / "openapi_snapshot.json"


def _load_full_openapi() -> dict:
    sys.path.insert(0, str(API_ROOT))
    # The app reads INTERNAL_API_KEY at import; any non-empty value lets it build. No
    # network or DB is touched by app.openapi().
    os.environ.setdefault("INTERNAL_API_KEY", "openapi-dump-placeholder")
    from app.main import app  # noqa: E402  (import after sys.path/env set)

    return app.openapi()


def _collect_refs(node: object, acc: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/"):
            acc.add(ref)
        for value in node.values():
            _collect_refs(value, acc)
    elif isinstance(node, list):
        for item in node:
            _collect_refs(item, acc)


def _prune(full: dict) -> dict:
    paths = {p: item for p, item in full.get("paths", {}).items() if p.startswith(SUBSET_PREFIX)}
    if not paths:
        raise SystemExit(f"no paths under {SUBSET_PREFIX!r} -- is the email router mounted?")

    # Transitively gather referenced components so the snapshot is self-contained.
    wanted: set[str] = set()
    _collect_refs(paths, wanted)
    all_components = full.get("components", {})
    kept_schemas: dict = {}
    frontier = list(wanted)
    while frontier:
        ref = frontier.pop()
        parts = ref[len("#/components/") :].split("/")
        if len(parts) != 2 or parts[0] != "schemas":
            continue
        name = parts[1]
        if name in kept_schemas:
            continue
        schema = all_components.get("schemas", {}).get(name)
        if schema is None:
            continue
        kept_schemas[name] = schema
        deeper: set[str] = set()
        _collect_refs(schema, deeper)
        frontier.extend(deeper)

    return {
        "openapi": full.get("openapi", "3.1.0"),
        "info": {
            "title": "janua internal email (MCP pilot subset)",
            "version": full.get("info", {}).get("version", "0"),
            "description": (
                "Generated subset of the janua OpenAPI covering /api/v1/internal/email. "
                "Source of truth for the MCP pilot tools. Regenerate with "
                "scripts/mcp_generate_openapi.py; CI fails on drift."
            ),
        },
        "paths": paths,
        "components": {"schemas": dict(sorted(kept_schemas.items()))},
    }


def _serialize(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed snapshot is stale")
    args = parser.parse_args(argv)

    doc = _prune(_load_full_openapi())
    rendered = _serialize(doc)

    if args.check:
        current = SNAPSHOT_PATH.read_text(encoding="utf-8") if SNAPSHOT_PATH.exists() else ""
        if current != rendered:
            print(
                "MCP OpenAPI snapshot drift: the live API no longer matches "
                f"{SNAPSHOT_PATH.relative_to(API_ROOT)}.\n"
                "Regenerate with: python scripts/mcp_generate_openapi.py",
                file=sys.stderr,
            )
            return 1
        print("MCP OpenAPI snapshot in sync")
        return 0

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {SNAPSHOT_PATH.relative_to(API_ROOT)} ({len(doc['paths'])} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
