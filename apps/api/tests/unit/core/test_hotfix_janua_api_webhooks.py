"""The webhooks hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-webhooks builds the image production runs plus
the webhook service and router of janua#817, because the promotion hold
(scripts/staging/promotion_runtime_guard.py) blocks normal promotions. These
tests keep the Dockerfile and its workflow from quietly widening, and pin that
this checkout's two files differ from production's copies by exactly the reviewed hunks.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-webhooks"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-webhooks.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
COPIED = {
    "apps/api/app/services/webhooks.py": "/app/app/services/",
    "apps/api/app/routers/v1/webhooks.py": "/app/app/routers/v1/",
}
DIFFS = {"apps/api/app/services/webhooks.py": "service.diff", "apps/api/app/routers/v1/webhooks.py": "router.diff"}
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

def test_base_is_the_json_encoding_hotfix_with_its_proven_sources():
    readme = (ROOT / "deployment/hotfix/janua-api-json-encoding/README.md").read_text()
    digest = WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1]
    assert re.search(rf"^\| Hotfix digest \| `{digest}`", readme, re.M)
    for key in ("BASE_SOURCE", "RESERVED_SOURCE", "CHATGPT_SOURCE", "ORG_LOGIN_SOURCE"):
        assert WORKFLOW["env"][key] == ROLE_SHAPE_WORKFLOW["env"][key], key
    for key in ("ROLE_SHAPE_SOURCE", "ENTITLEMENT_SOURCE", "RES2_SOURCE", "JSONENC_SOURCE"):
        assert re.fullmatch(r"[0-9a-f]{40}", WORKFLOW["env"][key]), key
    base_step = next(s for s in _steps() if s.get("name") == "Base image is BASE_SOURCE plus the earlier hotfix files")
    assert '"$JSONENC_SOURCE:apps/api/app/models/types.py"' in base_step["run"]
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
    assert WORKFLOW["permissions"] == {"contents": "read", "packages": "write", "id-token": "write"}
    scripts = "\n".join(step.get("run", "") for step in _steps())
    for forbidden in ("git push", "git commit", "k8s/overlays", "kubectl", "gh workflow run"):
        assert forbidden not in scripts, forbidden


def test_workflow_expects_exactly_the_copied_file():
    step = next(s for s in _steps() if s.get("name") == "Hotfix differs from the base by two files")
    for path in COPIED:
        inner = path.removeprefix("apps/api/app/")
        assert f"/tmp/hotfix/base/app/{inner} and /tmp/hotfix/new/app/{inner} differ" in step["run"]
        assert inner in step["run"]
    assert "for f in services/webhooks.py routers/v1/webhooks.py; do cmp /tmp/hotfix/new/app/$f apps/api/app/$f; done" in step["run"]
    assert "base_layers + 2" in step["run"]


def test_workflow_checks_source_delta_and_behaviour_before_signing():
    names = [step.get("name", "") for step in _steps()]
    order = [
        "Base image is BASE_SOURCE plus the earlier hotfix files",
        "The webhook service and router differ from production's only by the reviewed hunks",
        "Build and push",
        "Hotfix differs from the base by two files",
        "Discovery and client policy unchanged; the webhook service runs on the async session",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names


def test_the_two_files_in_this_checkout_differ_from_production_by_exactly_the_reviewed_hunks():
    """Production's copies are the files at BASE_SOURCE (no earlier hotfix overlays them). Computed with the same
    `git diff --no-index -U3` the workflow runs: diff(1) groups multi-hunk diffs differently on Mac and Linux."""
    import tempfile

    for path, diff_name in DIFFS.items():
        # Bytes end to end, like the workflow's shell: text mode would translate a carriage return in the file.
        base = subprocess.run(
            ["git", "show", f"{WORKFLOW['env']['BASE_SOURCE']}:{path}"], cwd=ROOT, check=True, capture_output=True
        ).stdout
        with tempfile.NamedTemporaryFile("wb", suffix=".py") as handle:
            handle.write(base)
            handle.flush()
            out = subprocess.run(
                ["git", "diff", "--no-index", "--no-color", "-U3", handle.name, str(ROOT / path)], capture_output=True
            ).stdout
        assert out[out.index(b"@@"):] == (HOTFIX / diff_name).read_bytes(), path


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard
