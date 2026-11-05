"""Execute rollback-prod.yml's real target resolution against disposable Git fixtures.

Rollback may only restore an image production has already run. The target
digest must have been the chosen component's digest in the production overlay
somewhere in main's first-parent history; anything else is a new image and must
go through promote-to-prod.yml and its guards.
"""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[5]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/rollback-prod.yml").read_text())
PROD = "k8s/overlays/production/kustomization.yaml"
STAGE = "k8s/overlays/staging/kustomization.yaml"

OLD = "sha256:" + "a" * 64  # production ran this api image before
CURRENT = "sha256:" + "b" * 64  # production runs this api image now
STAGED = "sha256:" + "c" * 64  # built and staged, never promoted
ADMIN = "sha256:" + "d" * 64  # production's admin image, never an api image


def overlay(api, admin=ADMIN, style="name-first"):
    """A production overlay in the shape the repo uses (or kustomize's sorted shape)."""
    entries = []
    for component, digest in (("admin", admin), ("api", api)):
        image = f"ghcr.io/madfam-org/janua-{component}"
        if style == "name-first":
            entries.append(f"  - name: {image}\n    newName: {image}\n    digest: {digest}\n")
        else:
            entries.append(f"- digest: {digest}\n  name: {image}\n  newName: {image}\n")
    return "images:\n" + "".join(entries)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def commit(work, message, **files):
    for rel, text in files.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(work, "add", ".")
    git(work, "commit", "-qm", message)


def resolve_script():
    return next(s["run"] for s in WORKFLOW["jobs"]["rollback"]["steps"] if s.get("id") == "target")


@pytest.fixture
def repo(tmp_path):
    """A clone whose origin/main has production at OLD, then at CURRENT."""

    def build(style="name-first"):
        origin = tmp_path / "origin.git"
        work = tmp_path / "work"
        git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
        git(tmp_path, "clone", "-q", str(origin), str(work))
        for args in [
            ["config", "user.name", "Synthetic fixture"],
            ["config", "user.email", "fixture@example.invalid"],
            ["config", "commit.gpgsign", "false"],
            ["symbolic-ref", "HEAD", "refs/heads/main"],
        ]:
            git(work, *args)
        commit(work, "synthetic seed", **{PROD: overlay(OLD, style=style), STAGE: overlay(STAGED)})
        commit(work, "synthetic promote", **{PROD: overlay(CURRENT, style=style)})
        git(work, "push", "-q", "origin", "HEAD:refs/heads/main")
        return work

    return build


def run(work, digest, component="api"):
    env = {
        **os.environ,
        "COMPONENT": component,
        "INPUT_DIGEST": digest,
        "GITHUB_OUTPUT": str(work / "outputs"),
    }
    return subprocess.run(
        ["bash", "-c", resolve_script()], cwd=work, env=env, capture_output=True, text=True
    )


def target_of(work):
    return (work / "outputs").read_text()


@pytest.mark.parametrize("style", ["name-first", "digest-first"])
def test_explicit_digest_production_ran_is_accepted(repo, style):
    work = repo(style)
    result = run(work, OLD)
    assert result.returncode == 0, result.stdout + result.stderr
    assert target_of(work) == f"target={OLD}\n"


def test_blank_digest_still_picks_the_previous_production_digest(repo):
    work = repo()
    result = run(work, "")
    assert result.returncode == 0, result.stdout + result.stderr
    assert target_of(work) == f"target={OLD}\n"


@pytest.mark.parametrize(
    "digest",
    [
        pytest.param(STAGED, id="staged-never-promoted"),
        pytest.param(ADMIN, id="another-components-digest"),
        pytest.param("sha256:" + "e" * 64, id="never-seen"),
    ],
)
def test_digest_production_never_ran_is_refused(repo, digest):
    work = repo()
    result = run(work, digest)
    assert result.returncode != 0
    assert "was never the production digest" in result.stderr
    assert not (work / "outputs").exists()


def test_overlay_edit_only_on_the_dispatch_ref_is_refused(repo):
    # Dispatching from a branch whose overlay names a new image must not make
    # that image "historical": the check reads main, not the checked-out ref.
    work = repo()
    commit(work, "unlanded overlay edit", **{PROD: overlay(STAGED)})
    result = run(work, STAGED)
    assert result.returncode != 0
    assert "was never the production digest" in result.stderr
    assert not (work / "outputs").exists()


def test_side_branch_state_main_never_held_is_refused(repo):
    # A merge can bring in a commit whose overlay main's tip never had.
    work = repo()
    git(work, "checkout", "-q", "-b", "side")
    commit(work, "side: pin staged image", **{PROD: overlay(STAGED)})
    commit(work, "side: restore", **{PROD: overlay(CURRENT)})
    git(work, "checkout", "-q", "main")
    git(work, "merge", "-q", "--no-ff", "side", "-m", "merge side")
    git(work, "push", "-q", "origin", "HEAD:refs/heads/main")
    # The side commit pinning STAGED is part of main's history...
    git(work, "merge-base", "--is-ancestor", "side~1", "origin/main")
    assert STAGED in git(work, "show", f"side~1:{PROD}").stdout
    result = run(work, STAGED)
    assert result.returncode != 0  # ...but production never ran it
    assert "was never the production digest" in result.stderr


@pytest.mark.parametrize("digest", ["sha256:abcd", OLD[:-1], OLD + "0", f" {OLD}"])
def test_malformed_digest_is_refused(repo, digest):
    work = repo()
    result = run(work, digest)
    assert result.returncode != 0
    assert "Invalid digest" in result.stdout + result.stderr
    assert not (work / "outputs").exists()


def test_checkout_keeps_full_history_for_the_target_check():
    checkout = next(
        s
        for s in WORKFLOW["jobs"]["rollback"]["steps"]
        if s.get("uses", "").startswith("actions/checkout@")
    )
    # A shallow clone would truncate the production history the check reads.
    assert checkout["with"]["fetch-depth"] == 0
