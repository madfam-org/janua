"""The second reservation-registry hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-reservations-2 builds the image production runs plus
the reservation registry from main (janua#799, #800, #801), because the
promotion hold (scripts/staging/promotion_runtime_guard.py) blocks normal
promotions. These tests keep the Dockerfile and its workflow from quietly
widening, and pin that the registry in this checkout only adds reservations to
the one production runs.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-reservations-2"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-reservations-2.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
COPIED = {"apps/api/app/core/reserved_oauth_boundaries.py": "/app/app/core/"}
ORG_BOUND_WORKFLOW = yaml.safe_load(
    (ROOT / ".github/workflows/hotfix-janua-api-org-bound-login.yml").read_text()
)
EXPECTED_ADDED = {
    "audiences": {"tlacuilo", "eido-api"},
    "scopes": {"tlacuilo:extract", "phynd-crm-pipeline:read"},
}


def _instructions() -> list[str]:
    lines = DOCKERFILE.read_text().splitlines()
    return [line for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _steps() -> list[dict]:
    return WORKFLOW["jobs"]["build"]["steps"]


def _record(field: str) -> str:
    readme = (HOTFIX / "README.md").read_text()
    row = re.search(rf"^\| {re.escape(field)} \| (.+) \|$", readme, re.M)
    assert row, f"exception record has no {field!r} row"
    return row.group(1)


def test_dockerfile_is_one_pinned_base_and_one_copy():
    instructions = _instructions()
    assert len(instructions) == 1 + len(COPIED), instructions
    base, *copies = instructions
    assert re.fullmatch(r"FROM ghcr\.io/madfam-org/janua-api@sha256:[0-9a-f]{64}", base), base
    assert copies == [f"COPY --chown=janua:python {src} {dst}" for src, dst in COPIED.items()]


def test_base_is_the_image_production_pins():
    """Before the pin PR, production runs the base; after it, production runs the
    hotfix digest the exception record names, which replaced exactly this base."""
    base = _instructions()[0].removeprefix("FROM ")
    assert WORKFLOW["env"]["BASE_IMAGE"] == base
    kustomization = (ROOT / "k8s/overlays/production/kustomization.yaml").read_text()
    block = re.search(r"name: ghcr\.io/madfam-org/janua-api\n(?:\s+\S.*\n){1,3}", kustomization)
    assert block, "production overlay has no janua-api image"
    digest = base.split("@", 1)[1]
    if digest in block.group(0):
        return
    pinned = re.search(r"sha256:[0-9a-f]{64}", _record("Hotfix digest"))
    assert pinned and pinned.group(0) in block.group(0), (
        "the hotfix must start from the production pin, or be the production pin"
    )
    assert digest in _record("Replaces"), "the pinned hotfix must replace this base"


def test_base_is_the_org_bound_hotfix_with_its_proven_sources():
    org_readme = (ROOT / "deployment/hotfix/janua-api-org-bound-login/README.md").read_text()
    digest = WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1]
    assert re.search(rf"^\| Hotfix digest \| `{digest}`", org_readme, re.M)
    for key in ("BASE_SOURCE", "RESERVED_SOURCE", "CHATGPT_SOURCE"):
        assert WORKFLOW["env"][key] == ORG_BOUND_WORKFLOW["env"][key], key
    assert re.fullmatch(r"[0-9a-f]{40}", WORKFLOW["env"]["ORG_BOUND_SOURCE"])
    assert WORKFLOW["env"]["DOCKERFILE"] == str(DOCKERFILE.relative_to(ROOT))
    assert WORKFLOW["env"]["HOTFIX_DIR"] == str(HOTFIX.relative_to(ROOT))
    for key in ("POLICY_DUMP", "REGISTRY_DUMP", "REGISTRY_COMPARE"):
        assert (ROOT / WORKFLOW["env"][key]).is_file(), key


def test_workflow_is_manual_and_from_main_only():
    triggers = WORKFLOW.get("on", WORKFLOW.get(True))  # PyYAML reads `on` as True
    assert set(triggers) == {"workflow_dispatch"}
    first = _steps()[0]
    assert first["if"] == "github.ref != 'refs/heads/main'"
    assert "exit 1" in first["run"]


def test_workflow_writes_only_to_the_registry():
    assert WORKFLOW["permissions"] == {"contents": "read", "packages": "write", "id-token": "write"}
    scripts = "\n".join(step.get("run", "") for step in _steps())
    for forbidden in ("git push", "git commit", "k8s/overlays", "kubectl", "gh workflow run"):
        assert forbidden not in scripts, forbidden


def test_workflow_expects_exactly_the_copied_file():
    step = next(s for s in _steps() if s.get("name") == "Hotfix differs from the base by one file")
    for path in COPIED:
        inner = path.removeprefix("apps/api/app/")
        assert f"/tmp/hotfix/base/app/{inner} and /tmp/hotfix/new/app/{inner} differ" in step["run"]
        assert f"cmp /tmp/hotfix/new/app/{inner} {path}" in step["run"]
    assert "base_layers + 1" in step["run"]


def test_workflow_checks_source_delta_and_behaviour_before_signing():
    names = [step.get("name", "") for step in _steps()]
    order = [
        "Base image is BASE_SOURCE plus the earlier hotfix files",
        "The registry changed only in janua#799, #800 and #801 since production's copy",
        "Build and push",
        "Hotfix differs from the base by one file",
        "Discovery and client policy unchanged; registry only tightens, by the expected values",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names


def _registry_at(ref: str) -> str:
    return subprocess.run(
        ["git", "show", f"{ref}:apps/api/app/core/reserved_oauth_boundaries.py"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout


def test_the_registry_in_this_checkout_only_adds_the_expected_reservations():
    """Production's copy (RESERVED_SOURCE) against this checkout: every value
    production reserves is still reserved, and the additions are exactly the
    four this hotfix exists for."""
    from app.core import reserved_oauth_boundaries as now

    namespace: dict = {}
    source = _registry_at(WORKFLOW["env"]["RESERVED_SOURCE"])
    # The production copy imports consent_purposes as this checkout does.
    exec(compile(source, "reserved_oauth_boundaries@production", "exec"), namespace)
    before_aud, before_scope = namespace["RESERVED_AUDIENCES"], namespace["RESERVED_SCOPES"]
    assert before_aud <= now.RESERVED_AUDIENCES, sorted(before_aud - now.RESERVED_AUDIENCES)
    assert before_scope <= now.RESERVED_SCOPES, sorted(before_scope - now.RESERVED_SCOPES)
    assert set(now.RESERVED_AUDIENCES - before_aud) == EXPECTED_ADDED["audiences"]
    assert set(now.RESERVED_SCOPES - before_scope) == EXPECTED_ADDED["scopes"]
    for name in ("RESERVED_AUDIENCE_PREFIXES", "RESERVED_SCOPE_SUFFIXES", "FIRST_PARTY_NAME_PREFIXES"):
        assert namespace[name] == getattr(now, name), name


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard
