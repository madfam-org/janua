"""The expires_in hotfix (row 16) stays one file wide.

deployment/hotfix/janua-api-expires-in builds production's image (row 15) plus
janua#860: the code and refresh grants announce the access token's real
lifetime instead of a literal 3600. These tests keep the Dockerfile and the
workflow from widening and pin the one change to janua#860's diff.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-expires-in"
ROW15 = ROOT / "deployment/hotfix/janua-api-roles-filter"
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/hotfix-janua-api-expires-in.yml").read_text())
ENV = WORKFLOW["env"]
MODULE = "routers/v1/oauth_provider_grants.py"
LITERAL = "expires_in=3600"
HELPER_USE = "expires_in=_access_token_expires_in(access_expires_at),"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def _recorded_digest(folder: Path) -> str | None:
    found = re.search(
        r"^\| Hotfix digest \| `(sha256:[0-9a-f]{64})`", (folder / "README.md").read_text(), re.M
    )
    return found.group(1) if found else None


def test_base_is_row_15():
    row15 = _recorded_digest(ROW15)
    assert row15, "row 15's record names no hotfix digest"
    assert ENV["BASE_IMAGE"] == f"ghcr.io/madfam-org/janua-api@{row15}"
    assert ENV["BASE_SIGNER"].endswith(
        "/.github/workflows/hotfix-janua-api-roles-filter.yml@refs/heads/main"
    )


def test_dockerfile_is_the_base_plus_the_one_module():
    lines = [
        line
        for line in (HOTFIX / "Dockerfile").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert ENV["MODULE"] == MODULE
    assert lines == [
        f"FROM {ENV['BASE_IMAGE']}",
        f"COPY --chown=janua:python apps/api/app/{MODULE} /app/app/{MODULE}",
    ]


def test_the_change_is_janua_860_and_nothing_else():
    previous, source = ENV["PREVIOUS"], ENV["SOURCE"]
    # Between production's code and SOURCE only this module changed.
    changed = _git("diff", "--name-only", previous, source, "--", "apps/api/app").split()
    assert changed == [f"apps/api/app/{MODULE}"]
    before = _git("show", f"{previous}:apps/api/app/{MODULE}")
    after = _git("show", f"{source}:apps/api/app/{MODULE}")
    assert before.count(LITERAL) == 2 and before.count("_access_token_expires_in") == 0
    assert after.count(LITERAL) == 0 and after.count(HELPER_USE) == 2
    numstat = _git("diff", "--numstat", previous, source, "--", f"apps/api/app/{MODULE}").split()
    assert numstat[:2] == ["18", "4"]


def test_the_working_tree_module_is_still_the_source():
    """A later edit of the module must come with a new row, not ride this one."""
    source = _git("show", f"{ENV['SOURCE']}:apps/api/app/{MODULE}")
    assert (ROOT / "apps/api/app" / MODULE).read_text() == source


def test_workflow_is_manual_from_main_and_signs_last():
    assert set(WORKFLOW[True]) == {"workflow_dispatch"}  # `on:` parses as True
    names = [step.get("name") for step in WORKFLOW["jobs"]["build"]["steps"]]
    assert names[0] == "Refuse anything but main"
    order = [
        "Dockerfile is the base plus the one module",
        "The shipped module is SOURCE's, and SOURCE is production's code plus janua#860",
        "Base image is row 15",
        "Build and push",
        "Hotfix differs from the base by the one module",
        "Discovery unchanged; expires_in is the token's lifetime on the hotfix and 3600 on the base",
        "Sign image with cosign",
    ]
    assert [n for n in names if n in order] == order


def test_the_in_image_check_reads_both_grants():
    check = (HOTFIX / "check_expires_in.py").read_text()
    for needle in (
        "_handle_authorization_code_grant",
        "_handle_refresh_token_grant",
        LITERAL,
        HELPER_USE.rstrip(","),
        "create_access_token",
    ):
        assert needle in check


def test_production_pin_is_untouched_by_this_folder():
    kustomization = (ROOT / "k8s/overlays/production/kustomization.yaml").read_text()
    block = re.search(r"name: ghcr\.io/madfam-org/janua-api\n(?:\s+\S.*\n){1,3}", kustomization)
    assert block
    expected = _recorded_digest(HOTFIX) or _recorded_digest(ROW15)
    assert expected in block.group(0)
