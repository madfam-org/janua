"""The ChatGPT-on-the-MAP hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-map-chatgpt builds the image production runs plus
two reviewed files (the protected-resource registry and the CIMD validation),
because the promotion hold (scripts/staging/promotion_runtime_guard.py) blocks
normal promotions. These tests keep the Dockerfile and its workflow from quietly
widening, and pin the policy comparison that refuses any image whose policy is
not production's plus ChatGPT on the MAP resource.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-map-chatgpt"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-map-chatgpt.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
COPIED = {
    "apps/api/app/core/protected_resources.py": "/app/app/core/",
    "apps/api/app/services/client_id_metadata.py": "/app/app/services/",
}
MAP = "https://map.creatumundo.mx/api/mcp"
SIM = "https://map-sim.creatumundo.mx/api/simulacion/mcp"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HOTFIX / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare_policy = _load("compare_policy")
dump_policy = _load("dump_policy")


def _instructions() -> list[str]:
    lines = DOCKERFILE.read_text().splitlines()
    return [
        line for line in lines if line.strip() and not line.lstrip().startswith("#")
    ]


def _steps() -> list[dict]:
    return WORKFLOW["jobs"]["build"]["steps"]


# --- Dockerfile and workflow shape -------------------------------------------


def test_dockerfile_is_one_pinned_base_and_one_copy_per_file():
    instructions = _instructions()
    assert len(instructions) == 1 + len(COPIED), instructions
    base, *copies = instructions
    assert re.fullmatch(
        r"FROM ghcr\.io/madfam-org/janua-api@sha256:[0-9a-f]{64}", base
    ), base
    assert copies == [
        f"COPY --chown=janua:python {src} {dst}" for src, dst in COPIED.items()
    ]


def _record(field: str) -> str:
    """A value from the README's exception record (`| Field | value |`)."""
    readme = (HOTFIX / "README.md").read_text()
    row = re.search(rf"^\| {re.escape(field)} \| (.+) \|$", readme, re.M)
    assert row, f"exception record has no {field!r} row"
    return row.group(1)


def test_base_is_the_image_production_pins():
    """Before the pin PR, production runs the base; after it, production runs the
    hotfix digest the exception record names, and that record says it replaced
    exactly this base. Any other production digest means the hotfix is stale."""
    base = _instructions()[0].removeprefix("FROM ")
    assert WORKFLOW["env"]["BASE_IMAGE"] == base
    kustomization = (ROOT / "k8s/overlays/production/kustomization.yaml").read_text()
    digest = base.split("@", 1)[1]
    block = re.search(
        r"name: ghcr\.io/madfam-org/janua-api\n(?:\s+\S.*\n){1,3}", kustomization
    )
    assert block, "production overlay has no janua-api image"
    if digest in block.group(0):
        return
    pinned = re.search(r"sha256:[0-9a-f]{64}", _record("Hotfix digest"))
    assert pinned and pinned.group(0) in block.group(
        0
    ), "the hotfix must start from the production pin, or be the production pin"
    assert digest in _record("Replaces"), "the pinned hotfix must replace this base"


def test_base_is_the_reserved_boundaries_image_with_its_proven_source():
    other = yaml.safe_load(
        (
            ROOT / ".github/workflows/hotfix-janua-api-reserved-boundaries.yml"
        ).read_text()
    )
    assert WORKFLOW["env"]["BASE_SOURCE"] == other["env"]["BASE_SOURCE"]
    assert re.fullmatch(r"[0-9a-f]{40}", WORKFLOW["env"]["RESERVED_SOURCE"])
    assert WORKFLOW["env"]["DOCKERFILE"] == str(DOCKERFILE.relative_to(ROOT))
    assert WORKFLOW["env"]["HOTFIX_DIR"] == str(HOTFIX.relative_to(ROOT))


def test_workflow_is_manual_and_from_main_only():
    triggers = WORKFLOW.get("on", WORKFLOW.get(True))  # PyYAML reads `on` as True
    assert set(triggers) == {"workflow_dispatch"}
    first = _steps()[0]
    assert first["if"] == "github.ref != 'refs/heads/main'"
    assert "exit 1" in first["run"]


def test_workflow_writes_only_to_the_registry():
    assert WORKFLOW["permissions"] == {
        "contents": "read",
        "packages": "write",
        "id-token": "write",
    }
    scripts = "\n".join(step.get("run", "") for step in _steps())
    for forbidden in (
        "git push",
        "git commit",
        "k8s/overlays",
        "kubectl",
        "gh workflow run",
    ):
        assert forbidden not in scripts, forbidden


def test_workflow_expects_exactly_the_copied_files_and_compares_each():
    step = next(
        s
        for s in _steps()
        if s.get("name") == "Hotfix differs from the base by two files"
    )
    for path in COPIED:
        inner = path.removeprefix("apps/api/app/")
        assert (
            f"/tmp/hotfix/base/app/{inner} and /tmp/hotfix/new/app/{inner} differ"
            in step["run"]
        )
        assert f"cmp /tmp/hotfix/new/app/{inner} {path}" in step["run"]
    assert "base_layers + 2" in step["run"]


def test_workflow_checks_source_delta_and_behaviour_before_signing():
    names = [step.get("name", "") for step in _steps()]
    order = [
        "Base image is BASE_SOURCE plus the reserved-boundaries files",
        "Build and push",
        "Hotfix differs from the base by two files",
        "Discovery unchanged; policy gains ChatGPT on the MAP only",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard


# --- The policy the image loads ----------------------------------------------


def test_dump_policy_against_this_checkout_shows_chatgpt():
    snapshot = dump_policy.snapshot()
    json.dumps(snapshot)  # serialisable
    assert snapshot["resources"][MAP]["cimd_hosts"] == ["chatgpt.com", "claude.ai"]
    assert snapshot["documents"] == {
        "chatgpt": "accepted:none",
        "claude": "accepted:none",
        "confidential": "refused:ClientMetadataError",
    }


def _policy(**over) -> dict:
    map_policy = {
        "scopes": ["map.cobro:read", "map.ops:read"],
        "access_token_ttl_seconds": 900,
        "cimd_hosts": ["claude.ai"],
        "cimd_client_ids": [
            "https://claude.ai/oauth/claude-code-client-metadata",
            "https://claude.ai/oauth/mcp-oauth-client-metadata",
        ],
        "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
        "allow_loopback_redirects": True,
    }
    sim_policy = {
        "scopes": ["map.sim:read", "map.sim:write"],
        "access_token_ttl_seconds": 900,
        "cimd_hosts": [],
        "cimd_client_ids": [],
        "redirect_uris": ["https://sim.creatumundo.mx/auth/mcp/callback"],
        "allow_loopback_redirects": False,
    }
    policy = {
        "resources": {MAP: map_policy, SIM: sim_policy},
        "redirect_origins": ["https://claude.ai", "https://sim.creatumundo.mx"],
        "documents": {
            "chatgpt": "refused:ClientMetadataError",
            "claude": "accepted:none",
            "confidential": "refused:ClientMetadataError",
        },
    }
    for key, value in over.items():
        policy[key] = value
    return policy


def _with_chatgpt() -> dict:
    new = json.loads(json.dumps(_policy()))
    m = new["resources"][MAP]
    m["cimd_hosts"] = sorted(m["cimd_hosts"] + ["chatgpt.com"])
    m["cimd_client_ids"] = sorted(
        m["cimd_client_ids"] + ["https://chatgpt.com/oauth/client.json"]
    )
    m["redirect_uris"] = sorted(
        m["redirect_uris"] + ["https://chatgpt.com/connector_platform_oauth_redirect"]
    )
    new["redirect_origins"] = [
        "https://chatgpt.com",
        "https://claude.ai",
        "https://sim.creatumundo.mx",
    ]
    new["documents"]["chatgpt"] = "accepted:none"
    return new


def test_compare_accepts_exactly_chatgpt_on_the_map():
    assert compare_policy.compare(_policy(), _with_chatgpt()) == []


def test_compare_refuses_an_unchanged_image():
    errors = compare_policy.compare(_policy(), _policy())
    assert errors and any("ChatGPT's document" in e for e in errors)


def test_compare_refuses_chatgpt_on_another_resource():
    new = _with_chatgpt()
    new["resources"][SIM]["cimd_hosts"] = ["chatgpt.com"]
    assert any(
        SIM in e and "cimd_hosts" in e for e in compare_policy.compare(_policy(), new)
    )


def test_compare_refuses_a_loosened_document_rule():
    new = _with_chatgpt()
    new["documents"]["confidential"] = "accepted:none"
    assert any("confidential-only" in e for e in compare_policy.compare(_policy(), new))


def test_compare_refuses_a_longer_token_or_a_new_scope():
    new = _with_chatgpt()
    new["resources"][MAP]["access_token_ttl_seconds"] = 3600
    new["resources"][MAP]["scopes"].append("map.write")
    errors = compare_policy.compare(_policy(), new)
    assert any("access_token_ttl_seconds" in e for e in errors)
    assert any("scopes" in e for e in errors)
