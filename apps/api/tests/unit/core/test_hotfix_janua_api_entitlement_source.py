"""The entitlement-source hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-entitlement-source builds the image production runs
plus the model fix of janua#811, because the promotion hold
(scripts/staging/promotion_runtime_guard.py) blocks normal promotions. These
tests keep the Dockerfile and its workflow from quietly widening, and pin that
this checkout's model differs from production's copy by exactly the reviewed hunk.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-entitlement-source"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-entitlement-source.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
COPIED = {"apps/api/app/models/__init__.py": "/app/app/models/"}
ROLE_SHAPE_WORKFLOW = yaml.safe_load(
    (ROOT / ".github/workflows/hotfix-janua-api-org-role-shape.yml").read_text()
)


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
    hotfix digest the exception record names, which replaced exactly this base,
    or a later hotfix reached from it through the exception records."""
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
    assert pinned, "exception record has no hotfix digest"
    assert digest in _record("Replaces"), "the pinned hotfix must replace this base"
    # Later owner-exception hotfixes may each start FROM the one before and
    # replace it in production. Follow the exception records from this hotfix's
    # digest: every step must be a record that says it replaced exactly the
    # previous digest, and the chain must end at what production pins.
    successors: dict[str, str] = {}
    for readme in sorted((ROOT / "deployment/hotfix").glob("*/README.md")):
        text = readme.read_text()
        replaces = re.search(r"^\| Replaces \| `(sha256:[0-9a-f]{64})`", text, re.M)
        successor = re.search(r"^\| Hotfix digest \| `(sha256:[0-9a-f]{64})`", text, re.M)
        if replaces and successor:
            successors[replaces.group(1)] = successor.group(1)
    current, seen = pinned.group(0), set()
    while current not in block.group(0):
        assert current in successors and current not in seen, (
            "the hotfix must start from the production pin, be the production pin, "
            "or be replaced in production through hotfixes whose records name each step"
        )
        seen.add(current)
        current = successors[current]

def test_base_sources_are_the_org_role_shape_hotfix_ones():
    readme = (ROOT / "deployment/hotfix/janua-api-org-role-shape/README.md").read_text()
    digest = WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1]
    assert re.search(rf"^\| Hotfix digest \| `{digest}`", readme, re.M)
    for key in ("BASE_SOURCE", "RESERVED_SOURCE", "CHATGPT_SOURCE", "ORG_LOGIN_SOURCE"):
        assert WORKFLOW["env"][key] == ROLE_SHAPE_WORKFLOW["env"][key], key
    assert re.fullmatch(r"[0-9a-f]{40}", WORKFLOW["env"]["ROLE_SHAPE_SOURCE"])
    assert WORKFLOW["env"]["DOCKERFILE"] == str(DOCKERFILE.relative_to(ROOT))
    assert WORKFLOW["env"]["HOTFIX_DIR"] == str(HOTFIX.relative_to(ROOT))
    assert WORKFLOW["env"]["MODELS_DIFF"] == str((HOTFIX / "models.diff").relative_to(ROOT))
    assert (ROOT / WORKFLOW["env"]["POLICY_DUMP"]).is_file()


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
        "The model differs from production's only by the entitlement source mapping",
        "Build and push",
        "Hotfix differs from the base by one file",
        "Discovery and client policy unchanged; the entitlement column maps to entitlement_source",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names


def test_the_model_in_this_checkout_differs_from_production_by_exactly_the_reviewed_hunk():
    """Production's copy is the file at BASE_SOURCE (no earlier hotfix overlays it)."""
    base = subprocess.run(
        ["git", "show", f"{WORKFLOW['env']['BASE_SOURCE']}:apps/api/app/models/__init__.py"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    now = (ROOT / "apps/api/app/models/__init__.py").read_text()
    import difflib

    hunk = "".join(difflib.unified_diff(base.splitlines(True), now.splitlines(True), n=3))
    body = hunk[hunk.index("@@"):]
    assert body == (HOTFIX / "models.diff").read_text()
    assert "name=\"entitlement_source\"" in body
    assert body.count("\n-") == 1, "exactly one production line is replaced"


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard
