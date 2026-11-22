"""The roles-filter hotfix (row 15) stays one file wide.

deployment/hotfix/janua-api-roles-filter builds production's image (row 14)
plus janua#801's `roles` filter in the OIDC handler, the hunk row 14 left out.
These tests keep the Dockerfile and the workflow from widening and pin the one
change to the reverse of row 14's reviewed hunk.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-roles-filter"
ROW14 = ROOT / "deployment/hotfix/janua-api-edge-hardening"
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/hotfix-janua-api-roles-filter.yml").read_text())
ENV = WORKFLOW["env"]
MODULE = "routers/v1/oauth_provider_shared.py"


def _row14_digest() -> str:
    record = (ROW14 / "README.md").read_text()
    found = re.search(r"^\| Hotfix digest \| `(sha256:[0-9a-f]{64})`", record, re.M)
    assert found, "row 14's record names no hotfix digest"
    return found.group(1)


def test_base_is_row_14():
    assert ENV["BASE_IMAGE"] == f"ghcr.io/madfam-org/janua-api@{_row14_digest()}"
    assert ENV["BASE_SIGNER"].endswith("/.github/workflows/hotfix-janua-api-edge-hardening.yml@refs/heads/main")


def test_dockerfile_is_the_base_plus_the_one_module():
    lines = [
        line
        for line in (HOTFIX / "Dockerfile").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert lines == [
        f"FROM {ENV['BASE_IMAGE']}",
        f"COPY --chown=janua:python apps/api/app/{MODULE} /app/app/{MODULE}",
    ]


def test_the_change_is_row_14s_hunk_reversed():
    source = subprocess.run(
        ["git", "show", f"{ENV['SOURCE']}:apps/api/app/{MODULE}"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    shipped = (ROW14 / "oauth_provider_shared.py.shipped").read_text()
    assert source != shipped
    assert 'entitlements["roles"] = organization_roles_for_roles_claim(' in source
    assert 'entitlements["roles"] = organization_roles_for_roles_claim(' not in shipped
    assert "roles = list({m.role for m in memberships if m.role})" in shipped
    # Against row 14's copy, the source differs by exactly row 14's reviewed hunk.
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
        tmp.write(source)
    diff = subprocess.run(
        ["git", "diff", "--no-index", "--no-color", "-U3", tmp.name, str(ROW14 / "oauth_provider_shared.py.shipped")],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout
    hunks = diff[diff.index("@@"):]
    assert hunks == (ROW14 / "oauth_provider_shared.diff").read_text()


def test_workflow_is_manual_from_main_and_signs_last():
    assert set(WORKFLOW[True]) == {"workflow_dispatch"}  # `on:` parses as True
    names = [step.get("name") for step in WORKFLOW["jobs"]["build"]["steps"]]
    assert names[0] == "Refuse anything but main"
    order = [
        "Dockerfile is the base plus the one module",
        "The shipped module is SOURCE's, and apps/api/app on main is SOURCE",
        "Base image is row 14",
        "Build and push",
        "Hotfix differs from the base by the one module",
        "Discovery unchanged; the OIDC handler filters on the hotfix and not on the base",
        "Sign image with cosign",
    ]
    assert [n for n in names if n in order] == order


def test_production_pin_is_untouched_by_this_folder():
    kustomization = (ROOT / "k8s/overlays/production/kustomization.yaml").read_text()
    block = re.search(r"name: ghcr\.io/madfam-org/janua-api\n(?:\s+\S.*\n){1,3}", kustomization)
    assert block
    record = (HOTFIX / "README.md").read_text()
    pinned = re.search(r"^\| Hotfix digest \| `(sha256:[0-9a-f]{64})`", record, re.M)
    expected = pinned.group(1) if pinned else _row14_digest()
    assert expected in block.group(0)
