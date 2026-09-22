"""The committed OpenAPI snapshot matches the live app (CI drift guard, live path).

Companion to ``scripts/mcp_generate_openapi.py --check``: if the email router's
request/response models change and the snapshot is not regenerated, this fails. Skipped
when the full app is not importable (so the offline unit run stays green); the CI job
that installs the full API deps runs it for real.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parents[3] / "scripts" / "mcp_generate_openapi.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("mcp_generate_openapi", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_snapshot_matches_live_app():
    module = _load_script_module()
    try:
        full = module._load_full_openapi()
    except Exception as exc:  # pragma: no cover - depends on install
        pytest.skip(f"live app not importable ({type(exc).__name__}); run the full-deps CI job")
    rendered = module._serialize(module._prune(full))
    current = module.SNAPSHOT_PATH.read_text(encoding="utf-8")
    assert current == rendered, (
        "app/mcp/openapi_snapshot.json is stale. Regenerate with "
        "`python scripts/mcp_generate_openapi.py` and commit."
    )
