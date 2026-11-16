"""The primary-organization hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-primary-organization builds the image production
runs plus janua#822 (an operator-set primary organization), because the
promotion hold (scripts/staging/promotion_runtime_guard.py) blocks normal
promotions. These tests keep the Dockerfile and its workflow from quietly
widening, pin that this checkout's changed files differ from production's
copies by exactly the reviewed hunks, and run the behaviour check the workflow
runs in the built image.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-primary-organization"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-primary-organization.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
WEBHOOKS_WORKFLOW = yaml.safe_load(
    (ROOT / ".github/workflows/hotfix-janua-api-webhooks.yml").read_text()
)
COPIED = {
    "apps/api/app/models/user_primary_organization.py": "/app/app/models/",
    "apps/api/app/schemas/primary_organization.py": "/app/app/schemas/",
    "apps/api/app/routers/v1/internal_primary_organization.py": "/app/app/routers/v1/",
    "apps/api/app/services/org_claims_service.py": "/app/app/services/",
    "apps/api/app/services/audit_logger.py": "/app/app/services/",
    "deployment/hotfix/janua-api-primary-organization/main.py": "/app/app/",
    "apps/api/alembic/versions/022_user_primary_organization.py": "/app/alembic/versions/",
}
# (production's copy as `source key:path`, the file the image gets, the reviewed hunk)
HUNKS = [
    ("ROLE_SHAPE_SOURCE", "apps/api/app/services/org_claims_service.py",
     ROOT / "apps/api/app/services/org_claims_service.py", "claims.diff"),
    ("BASE_SOURCE", "apps/api/app/services/audit_logger.py",
     ROOT / "apps/api/app/services/audit_logger.py", "audit.diff"),
    ("BASE_SOURCE", "apps/api/app/main.py", HOTFIX / "main.py", "main.diff"),
]


def _instructions() -> list[str]:
    lines = DOCKERFILE.read_text().splitlines()
    return [line for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _steps() -> list[dict]:
    return WORKFLOW["jobs"]["build"]["steps"]


def _step(name: str) -> dict:
    return next(s for s in _steps() if s.get("name") == name)


def _record(field: str) -> str:
    readme = (HOTFIX / "README.md").read_text()
    row = re.search(rf"^\| {re.escape(field)} \| (.+) \|$", readme, re.M)
    assert row, f"exception record has no {field!r} row"
    return row.group(1)


def test_dockerfile_is_one_pinned_base_and_one_copy_per_file():
    instructions = _instructions()
    assert len(instructions) == 1 + len(COPIED), instructions
    base, *copies = instructions
    assert re.fullmatch(r"FROM ghcr\.io/madfam-org/janua-api@sha256:[0-9a-f]{64}", base), base
    assert copies == [f"COPY --chown=janua:python {src} {dst}" for src, dst in COPIED.items()]
    # The hot User model file is not part of this hotfix.
    assert "models/__init__.py" not in DOCKERFILE.read_text()


def test_base_is_the_image_production_pins():
    """Before the pin PR, production runs the base; after it, production runs the
    hotfix digest the exception record names, which replaced exactly this base,
    or a later hotfix reached from it through the exception records."""
    base = _instructions()[0].removeprefix("FROM ")
    assert WORKFLOW["env"]["BASE_IMAGE"] == base
    kustomization = (ROOT / "k8s/overlays/production/kustomization.yaml").read_text()
    block = re.search(r"name: ghcr\.io/madfam-org/janua-api\n(?:\s+\S.*\n){1,3}", kustomization)
    assert block, "production overlay has no janua-api image"
    digest = base.split("@", 1)[1]
    if digest in block.group(0):
        return
    pinned = re.search(r"sha256:[0-9a-f]{64}", _record("Hotfix digest"))
    assert pinned, "exception record has no hotfix digest"
    assert digest in _record("Replaces"), "the pinned hotfix must replace this base"
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


def test_base_is_the_webhooks_hotfix_with_its_proven_sources():
    readme = (ROOT / "deployment/hotfix/janua-api-webhooks/README.md").read_text()
    digest = WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1]
    assert re.search(rf"^\| Hotfix digest \| `{digest}`", readme, re.M)
    for key in (
        "BASE_SOURCE", "RESERVED_SOURCE", "CHATGPT_SOURCE", "ORG_LOGIN_SOURCE",
        "ROLE_SHAPE_SOURCE", "ENTITLEMENT_SOURCE", "RES2_SOURCE", "JSONENC_SOURCE",
    ):
        assert WORKFLOW["env"][key] == WEBHOOKS_WORKFLOW["env"][key], key
    built = re.search(r"^\| Built by \| .*`main` `([0-9a-f]{7,40})`", readme, re.M)
    assert built and WORKFLOW["env"]["WEBHOOKS_SOURCE"].startswith(built.group(1))
    base_step = _step("Base image is BASE_SOURCE plus the earlier hotfix files")
    webhooks_base = next(
        s for s in WEBHOOKS_WORKFLOW["jobs"]["build"]["steps"]
        if s.get("name") == "Base image is BASE_SOURCE plus the earlier hotfix files"
    )
    # Every overlay the webhooks hotfix proved is proved again, plus its own files.
    for line in webhooks_base["run"].splitlines():
        if "git show" in line:
            assert line.strip() in base_step["run"], line
    assert '"$WEBHOOKS_SOURCE:apps/api/app/$f"' in base_step["run"]
    assert "/tmp/hotfix/base/versions" in base_step["run"]
    assert WORKFLOW["env"]["DOCKERFILE"] == str(DOCKERFILE.relative_to(ROOT))
    assert WORKFLOW["env"]["HOTFIX_DIR"] == str(HOTFIX.relative_to(ROOT))
    assert (ROOT / WORKFLOW["env"]["POLICY_DUMP"]).is_file()
    assert (ROOT / WORKFLOW["env"]["CHECK"]).is_file()


def test_workflow_is_manual_and_from_main_only():
    triggers = WORKFLOW.get("on", WORKFLOW.get(True))  # PyYAML reads `on` as True
    assert set(triggers) == {"workflow_dispatch"}
    first = _steps()[0]
    assert first["if"] == "github.ref != 'refs/heads/main'"
    assert "exit 1" in first["run"]


def test_workflow_writes_only_to_the_registry():
    assert WORKFLOW["permissions"] == {"contents": "read", "packages": "write", "id-token": "write"}
    scripts = "\n".join(step.get("run", "") for step in _steps())
    for forbidden in ("git push", "git commit", "k8s/overlays", "kubectl", "gh workflow run", "psql"):
        assert forbidden not in scripts, forbidden


def test_workflow_expects_exactly_the_seven_files():
    step = _step("Hotfix differs from the base by seven files")
    for changed in ("main.py", "services/audit_logger.py", "services/org_claims_service.py"):
        assert f"/tmp/hotfix/base/app/{changed} and /tmp/hotfix/new/app/{changed} differ" in step["run"]
    for directory, name in (
        ("app/models", "user_primary_organization.py"),
        ("app/routers/v1", "internal_primary_organization.py"),
        ("app/schemas", "primary_organization.py"),
        ("versions", "022_user_primary_organization.py"),
    ):
        assert f"Only in /tmp/hotfix/new/{directory}: {name}" in step["run"]
    assert "base_layers + 7" in step["run"]
    assert 'cmp /tmp/hotfix/new/app/main.py "$HOTFIX_DIR/main.py"' in step["run"]


def test_workflow_checks_source_delta_and_behaviour_before_signing():
    names = [step.get("name", "") for step in _steps()]
    order = [
        "Base image is BASE_SOURCE plus the earlier hotfix files",
        "The changed files differ from production's only by the reviewed hunks",
        "Build and push",
        "Hotfix differs from the base by seven files",
        "Discovery and client policy unchanged; a primary organization carries its app role",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names
    behaviour = _step(order[4])["run"]
    assert 'base["primary_resolves_with_app_role"] is False' in behaviour
    assert "all(new.values())" in behaviour


def test_the_changed_files_differ_from_production_by_exactly_the_reviewed_hunks():
    """Computed with the same `git diff --no-index -U3` the workflow runs (diff(1)
    groups hunks differently on Mac and Linux), bytes end to end."""
    for source_key, prod_path, image_file, diff_name in HUNKS:
        base = subprocess.run(
            ["git", "show", f"{WORKFLOW['env'][source_key]}:{prod_path}"],
            cwd=ROOT, check=True, capture_output=True,
        ).stdout
        with tempfile.NamedTemporaryFile("wb", suffix=".py") as handle:
            handle.write(base)
            handle.flush()
            out = subprocess.run(
                ["git", "diff", "--no-index", "--no-color", "-U3", handle.name, str(image_file)],
                capture_output=True,
            ).stdout
        assert out[out.index(b"@@"):] == (HOTFIX / diff_name).read_bytes(), diff_name


def test_main_diff_is_only_the_registration_main_carries():
    hunk = (HOTFIX / "main.diff").read_text().splitlines()
    assert not [line for line in hunk if line.startswith("-")], "main.diff removes production lines"
    added = "\n".join(line[1:] for line in hunk if line.startswith("+")) + "\n"
    assert "internal_primary_organization" in added
    assert added in (ROOT / "apps/api/app/main.py").read_text()


def test_check_script_passes_in_this_checkout():
    """The script the workflow runs in the built image, run here: on this
    checkout every property it reports must hold."""
    import contextlib
    import io
    import json
    import runpy

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        runpy.run_path(str(HOTFIX / "check_primary_org.py"))
    line = next(row for row in out.getvalue().splitlines() if row.startswith("PRIMARY_ORG="))
    report = json.loads(line.removeprefix("PRIMARY_ORG="))
    assert report and all(report.values()), report


def test_exception_record_names_the_owner_go_and_its_scope():
    approved = _record("Approved by")
    assert "2026-11-16" in approved
    assert "«You have my GO for the hotfix»" in approved
    assert "primary-organization hotfix only" in approved
    assert WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1] in _record("Replaces")


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard
