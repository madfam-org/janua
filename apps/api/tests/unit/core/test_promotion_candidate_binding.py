"""Execute the real workflow guards using disposable source-only fixtures."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[5]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/promote-to-prod.yml").read_text())
DIGEST = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64


def overlay(digest, image="ghcr.io/madfam-org/janua-api"):
    return f"images:\n- digest: {digest}\n  name: {image}\n  newName: {image}\n"


def resolve_script():
    return next(s["run"] for s in WORKFLOW["jobs"]["validate"]["steps"] if s.get("id") == "resolve")


def patch_script():
    step = next(
        s for s in WORKFLOW["jobs"]["promote"]["steps"] if "run" in s and "patch_prod()" in s["run"]
    )
    function = step["run"].split("patch_prod() {", 1)[1].split("\n}\n", 1)[0]
    return "set -euo pipefail\npatch_prod() {" + function + "\n}\npatch_prod\n"


@pytest.fixture
def source(tmp_path):
    stage = tmp_path / "k8s/overlays/staging/kustomization.yaml"
    prod = tmp_path / "k8s/overlays/production/kustomization.yaml"
    stage.parent.mkdir(parents=True)
    prod.parent.mkdir(parents=True)
    stage.write_text(overlay(DIGEST))
    prod.write_text(overlay(OTHER))
    for args in [
        ["init", "-q"],
        ["config", "user.name", "Synthetic fixture"],
        ["config", "user.email", "fixture@example.invalid"],
        ["add", "."],
        ["commit", "-qm", "synthetic stage pin"],
    ]:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path, stage, prod


def run(script, cwd, **changes):
    env = {
        **os.environ,
        "EVENT": "workflow_dispatch",
        "COMPONENT": "api",
        "INPUT_DIGEST": "",
        "INPUT_REASON": "Synthetic guard qualification",
        "INPUT_BREAK_GLASS_WITHOUT_SOAK": "false",
        "MIN_SOAK_MIN": "0",  # Test source binding, not a runtime-soak claim.
        "GITHUB_OUTPUT": str(cwd / "outputs"),
        "API_DIGEST": DIGEST,
        "ADMIN_DIGEST": "",
        "DASHBOARD_DIGEST": "",
        "DOCS_DIGEST": "",
        "WEBSITE_DIGEST": "",
        **changes,
    }
    return subprocess.run(["bash", "-c", script], cwd=cwd, env=env, capture_output=True, text=True)


@pytest.mark.parametrize("requested", ["", DIGEST])
def test_resolve_accepts_only_current_stage(source, requested):
    cwd, _, _ = source
    result = run(resolve_script(), cwd, INPUT_DIGEST=requested)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"api_digest={DIGEST}" in (cwd / "outputs").read_text()


def test_explicit_historical_digest_cannot_select_an_unstaged_image(source):
    cwd, stage, _ = source
    # Both pins exist in Git history; only the current one is eligible.
    stage.write_text(overlay(OTHER))
    subprocess.run(["git", "add", "."], cwd=cwd, check=True)
    subprocess.run(["git", "commit", "-qm", "newer synthetic pin"], cwd=cwd, check=True)
    result = run(resolve_script(), cwd, INPUT_DIGEST=DIGEST)
    assert result.returncode != 0
    assert "differs from the current staging pin" in result.stderr
    assert not (cwd / "outputs").exists()


def test_truncated_stage_digest_is_rejected(source):
    cwd, stage, _ = source
    stage.write_text(overlay("sha256:abcd"))
    result = run(resolve_script(), cwd)
    assert result.returncode != 0
    assert "Invalid api digest" in result.stderr


def test_fresh_main_stage_change_cannot_write_production(source):
    cwd, stage, prod = source
    before = prod.read_text()
    stage.write_text(overlay(OTHER))
    result = run(patch_script(), cwd)
    assert result.returncode != 0
    assert "Current staging candidate changed" in result.stderr
    assert prod.read_text() == before


@pytest.mark.parametrize("kind", ["missing", "duplicate", "different-image"])
def test_unproved_fresh_main_stage_cannot_write_production(source, kind):
    cwd, stage, prod = source
    before = prod.read_text()
    if kind == "missing":
        stage.unlink()
    elif kind == "duplicate":
        stage.write_text(overlay(DIGEST) + overlay(DIGEST).removeprefix("images:\n"))
    else:
        stage.write_text(overlay(DIGEST, "ghcr.io/madfam-org/janua-api-other"))
    result = run(patch_script(), cwd)
    assert result.returncode != 0
    assert prod.read_text() == before


def test_fresh_main_matching_pin_changes_only_api(source):
    cwd, _, prod = source
    extra = "- digest: " + OTHER + "\n  name: ghcr.io/madfam-org/janua-admin\n"
    prod.write_text(prod.read_text() + extra)
    result = run(patch_script(), cwd)
    assert result.returncode == 0, result.stdout + result.stderr
    assert prod.read_text() == overlay(DIGEST) + extra
