"""The org-bound-login hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-org-bound-login builds the image production runs
plus the two reviewed files of janua#795, because the promotion hold
(scripts/staging/promotion_runtime_guard.py) blocks normal promotions. These
tests keep the Dockerfile and its workflow from quietly widening.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-org-bound-login"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-org-bound-login.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
COPIED = {
    "apps/api/app/auth/tenant_login_context.py": "/app/app/auth/",
    "apps/api/app/auth/hosted_security.py": "/app/app/auth/",
}
CHATGPT_WORKFLOW = yaml.safe_load(
    (ROOT / ".github/workflows/hotfix-janua-api-map-chatgpt.yml").read_text()
)


def _instructions() -> list[str]:
    lines = DOCKERFILE.read_text().splitlines()
    return [
        line for line in lines if line.strip() and not line.lstrip().startswith("#")
    ]


def _steps() -> list[dict]:
    return WORKFLOW["jobs"]["build"]["steps"]


def _record(field: str) -> str:
    readme = (HOTFIX / "README.md").read_text()
    row = re.search(rf"^\| {re.escape(field)} \| (.+) \|$", readme, re.M)
    assert row, f"exception record has no {field!r} row"
    return row.group(1)


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


def test_base_is_the_image_production_pins():
    """Before the pin PR, production runs the base; after it, production runs the
    hotfix digest the exception record names, which replaced exactly this base."""
    base = _instructions()[0].removeprefix("FROM ")
    assert WORKFLOW["env"]["BASE_IMAGE"] == base
    kustomization = (ROOT / "k8s/overlays/production/kustomization.yaml").read_text()
    block = re.search(
        r"name: ghcr\.io/madfam-org/janua-api\n(?:\s+\S.*\n){1,3}", kustomization
    )
    assert block, "production overlay has no janua-api image"
    digest = base.split("@", 1)[1]
    if digest in block.group(0):
        return
    pinned = re.search(r"sha256:[0-9a-f]{64}", _record("Hotfix digest"))
    assert pinned and pinned.group(0) in block.group(
        0
    ), "the hotfix must start from the production pin, or be the production pin"
    assert digest in _record("Replaces"), "the pinned hotfix must replace this base"


def test_base_is_the_chatgpt_hotfix_with_its_proven_sources():
    chatgpt_readme = (ROOT / "deployment/hotfix/janua-api-map-chatgpt/README.md").read_text()
    digest = WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1]
    assert re.search(rf"^\| Hotfix digest \| `{digest}`", chatgpt_readme, re.M)
    for key in ("BASE_SOURCE", "RESERVED_SOURCE"):
        assert WORKFLOW["env"][key] == CHATGPT_WORKFLOW["env"][key]
    assert re.fullmatch(r"[0-9a-f]{40}", WORKFLOW["env"]["CHATGPT_SOURCE"])
    assert WORKFLOW["env"]["DOCKERFILE"] == str(DOCKERFILE.relative_to(ROOT))
    assert WORKFLOW["env"]["HOTFIX_DIR"] == str(HOTFIX.relative_to(ROOT))
    assert (ROOT / WORKFLOW["env"]["POLICY_DUMP"]).is_file()


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
    for forbidden in ("git push", "git commit", "k8s/overlays", "kubectl", "gh workflow run"):
        assert forbidden not in scripts, forbidden


def test_workflow_expects_exactly_the_copied_files_and_compares_each():
    step = next(
        s for s in _steps() if s.get("name") == "Hotfix differs from the base by two files"
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
        "Base image is BASE_SOURCE plus the earlier hotfix files",
        "The copied files changed only in janua#795 since production's source",
        "Build and push",
        "Hotfix differs from the base by two files",
        "Discovery and client policy unchanged; login gains the platform fallback",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names


def test_check_login_reports_the_fallback_in_this_checkout():
    from app.auth import hosted_security, tenant_login_context

    assert hasattr(tenant_login_context, "_platform_member_by_email")
    assert hasattr(tenant_login_context, "user_in_client_pool")
    assert hasattr(tenant_login_context, "require_client_membership")
    import inspect

    assert "user_in_client_pool" in inspect.getsource(hosted_security)


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard
