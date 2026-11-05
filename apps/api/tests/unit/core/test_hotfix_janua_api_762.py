"""The janua#762 hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-762 builds the image production runs plus one file,
because the promotion hold (scripts/staging/promotion_runtime_guard.py) blocks
normal promotions and promoting main would ship #758. These tests keep the
Dockerfile and its workflow from quietly widening: one pinned base, one copied
file, manual dispatch from main only, and no write anywhere but the registry.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
DOCKERFILE = ROOT / "deployment/hotfix/janua-api-762/Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-762.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
PATCHED = "apps/api/app/core/oauth_metadata.py"


def _instructions() -> list[str]:
    lines = DOCKERFILE.read_text().splitlines()
    return [line for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _run_scripts() -> str:
    steps = WORKFLOW["jobs"]["build"]["steps"]
    return "\n".join(step.get("run", "") for step in steps)


def test_dockerfile_is_one_pinned_base_and_one_file():
    instructions = _instructions()
    assert len(instructions) == 2, instructions
    base, copy = instructions
    assert re.fullmatch(r"FROM ghcr\.io/madfam-org/janua-api@sha256:[0-9a-f]{64}", base), base
    assert copy == f"COPY --chown=janua:python {PATCHED} /app/app/core/oauth_metadata.py"


def test_workflow_verifies_the_base_the_dockerfile_pins():
    base = _instructions()[0].removeprefix("FROM ")
    assert WORKFLOW["env"]["BASE_IMAGE"] == base
    assert WORKFLOW["env"]["DOCKERFILE"] == str(DOCKERFILE.relative_to(ROOT))
    assert WORKFLOW["env"]["PATCHED_FILE"] == PATCHED
    assert re.fullmatch(r"[0-9a-f]{40}", WORKFLOW["env"]["BASE_SOURCE"])


def test_workflow_is_manual_and_from_main_only():
    # PyYAML reads the bare key `on` as True.
    triggers = WORKFLOW.get("on", WORKFLOW.get(True))
    assert set(triggers) == {"workflow_dispatch"}
    first = WORKFLOW["jobs"]["build"]["steps"][0]
    assert first["if"] == "github.ref != 'refs/heads/main'"
    assert "exit 1" in first["run"]


def test_workflow_writes_only_to_the_registry():
    assert WORKFLOW["permissions"] == {
        "contents": "read",
        "packages": "write",
        "id-token": "write",
    }
    scripts = _run_scripts()
    for forbidden in ("git push", "git commit", "k8s/overlays", "kubectl", "gh workflow run"):
        assert forbidden not in scripts, forbidden


def test_discovery_check_uses_a_driver_the_production_image_has():
    """The production image installs requirements.txt only: asyncpg, not aiosqlite.

    The first dispatch (run 41952923922) failed importing the app with a
    sqlite+aiosqlite URL, a test-only driver.
    """
    step = next(
        s
        for s in WORKFLOW["jobs"]["build"]["steps"]
        if s.get("name") == "Discovery document loses registration_endpoint and nothing else"
    )
    urls = re.findall(r"DATABASE_URL='([^']*)'", step["run"])
    assert urls and all(url.startswith("postgresql+asyncpg://") for url in urls), urls
    requirements = (ROOT / "apps/api/requirements.txt").read_text()
    assert re.search(r"^asyncpg\b", requirements, re.M)


def test_workflow_checks_source_delta_and_discovery_before_signing():
    names = [step.get("name", "") for step in WORKFLOW["jobs"]["build"]["steps"]]
    order = [
        "Base image is BASE_SOURCE",
        "Build and push",
        "Hotfix differs from the base by one file",
        "Discovery document loses registration_endpoint and nothing else",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names
