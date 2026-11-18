"""The public-silent-auth hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-public-silent-auth builds the image production runs
plus janua#833, because the promotion hold
(scripts/staging/promotion_runtime_guard.py) blocks normal promotions. These
tests keep the Dockerfile and its workflow from quietly widening, pin that the
shipped file differs from production's copy by exactly the reviewed hunks (and
is production's copy plus the merge, nothing else), and run the behaviour check
the workflow runs in the built image.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-public-silent-auth"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-public-silent-auth.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
HOSTED_WORKFLOW = yaml.safe_load(
    (ROOT / ".github/workflows/hotfix-janua-api-hosted-locale.yml").read_text()
)
SHIPPED = HOTFIX / "oauth_provider.py.shipped"
PROD_PATH = "apps/api/app/routers/v1/oauth_provider.py"
COPIED = {
    "deployment/hotfix/janua-api-public-silent-auth/oauth_provider.py.shipped": "/app/app/routers/v1/oauth_provider.py",
}


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def _production_copy() -> bytes:
    """Production's oauth_provider.py: the hosted-locale hotfix's shipped copy."""
    env = WORKFLOW["env"]
    return _git("show", f"{env['HOSTED_SOURCE']}:{env['HOSTED_DIR']}/oauth_provider.py.shipped")


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


def _check_output() -> dict[str, dict]:
    import contextlib
    import io
    import json
    import runpy

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        runpy.run_path(str(HOTFIX / "check_silent_auth.py"))
    lines = out.getvalue().splitlines()
    return {
        key: json.loads(
            next(row for row in lines if row.startswith(key + "=")).removeprefix(key + "=")
        )
        for key in ("UNCHANGED", "SILENT")
    }


def test_dockerfile_is_one_pinned_base_and_one_copy_per_file():
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


def test_base_is_the_hosted_locale_hotfix_with_its_proven_sources():
    readme = (ROOT / "deployment/hotfix/janua-api-hosted-locale/README.md").read_text()
    digest = WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1]
    assert re.search(rf"^\| Hotfix digest \| `{digest}`", readme, re.M)
    for key in (
        "BASE_SOURCE",
        "RESERVED_SOURCE",
        "CHATGPT_SOURCE",
        "ORG_LOGIN_SOURCE",
        "ROLE_SHAPE_SOURCE",
        "ENTITLEMENT_SOURCE",
        "RES2_SOURCE",
        "JSONENC_SOURCE",
        "WEBHOOKS_SOURCE",
        "PRIMARY_SOURCE",
        "CONTAIN_SOURCE",
        "PRIMARY_DIR",
        "POLICY_DUMP",
    ):
        assert WORKFLOW["env"][key] == HOSTED_WORKFLOW["env"][key], key
    assert WORKFLOW["env"]["HOSTED_DIR"] == HOSTED_WORKFLOW["env"]["HOTFIX_DIR"]
    built = re.search(r"^\| Built by \| .*`main` `([0-9a-f]{7,40})`", readme, re.M)
    assert built and WORKFLOW["env"]["HOSTED_SOURCE"].startswith(built.group(1))
    name = "Base image is BASE_SOURCE plus the earlier hotfix files"
    base_step = _step(name)
    hosted_base = next(
        s for s in HOSTED_WORKFLOW["jobs"]["build"]["steps"] if s.get("name") == name
    )
    # Every overlay the hosted-locale hotfix proved is proved again, plus its own files.
    for line in hosted_base["run"].splitlines():
        if "git show" in line or line.strip().startswith("for f in"):
            assert line.strip() in base_step["run"], line
    assert "for f in auth/hosted_locale.py routers/v1/auth.py; do" in base_step["run"]
    assert '"$HOSTED_SOURCE:apps/api/app/$f"' in base_step["run"]
    assert '"$HOSTED_SOURCE:$HOSTED_DIR/oauth_provider.py.shipped"' in base_step["run"]
    # The hosted-locale overlay comes after the overlays it supersedes.
    assert base_step["run"].index("$HOSTED_SOURCE") > base_step["run"].index("$CONTAIN_SOURCE")
    assert base_step["run"].index("$HOSTED_SOURCE") > base_step["run"].index("$RES2_SOURCE")
    assert WORKFLOW["env"]["DOCKERFILE"] == str(DOCKERFILE.relative_to(ROOT))
    assert WORKFLOW["env"]["HOTFIX_DIR"] == str(HOTFIX.relative_to(ROOT))
    assert (ROOT / WORKFLOW["env"]["POLICY_DUMP"]).is_file()
    assert (ROOT / WORKFLOW["env"]["CHECK"]).is_file()


def test_production_copy_is_the_one_hosted_locale_ships():
    """The hosted-locale folder on main still holds the copy production runs."""
    hosted = ROOT / WORKFLOW["env"]["HOSTED_DIR"] / "oauth_provider.py.shipped"
    assert hosted.read_bytes() == _production_copy()


def test_workflow_is_manual_and_from_main_only():
    triggers = WORKFLOW.get("on", WORKFLOW.get(True))  # PyYAML reads `on` as True
    assert set(triggers) == {"workflow_dispatch"}
    first = _steps()[0]
    assert first["if"] == "github.ref != 'refs/heads/main'"
    assert "exit 1" in first["run"]


def test_workflow_writes_only_to_the_registry():
    assert WORKFLOW["permissions"] == {"contents": "read", "packages": "write", "id-token": "write"}
    scripts = "\n".join(step.get("run", "") for step in _steps())
    for forbidden in (
        "git push",
        "git commit",
        "k8s/overlays",
        "kubectl",
        "gh workflow run",
        "psql",
    ):
        assert forbidden not in scripts, forbidden


def test_workflow_expects_exactly_the_one_file():
    step = _step("Hotfix differs from the base by one file")
    assert (
        'expected="Files /tmp/hotfix/base/app/routers/v1/oauth_provider.py and '
        '/tmp/hotfix/new/app/routers/v1/oauth_provider.py differ"'
    ) in step["run"]
    assert (
        'cmp /tmp/hotfix/new/app/routers/v1/oauth_provider.py "$HOTFIX_DIR/oauth_provider.py.shipped"'
        in step["run"]
    )
    assert "base_layers + 1" in step["run"]
    assert "Only in" not in step["run"]


def test_workflow_checks_source_delta_and_behaviour_before_signing():
    names = [step.get("name", "") for step in _steps()]
    order = [
        "Base image is BASE_SOURCE plus the earlier hotfix files",
        "The changed file differs from production's only by the reviewed hunks",
        "The shipped file is production's copy plus janua#833",
        "Build and push",
        "Hotfix differs from the base by one file",
        "Discovery, client policy and existing first-party trust unchanged; marked public clients decided per request",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names
    behaviour = _step(order[5])["run"]
    assert "cmp /tmp/hotfix/base-metadata.json /tmp/hotfix/new-metadata.json" in behaviour
    assert "cmp /tmp/hotfix/base-policy.json /tmp/hotfix/new-policy.json" in behaviour
    assert "cmp /tmp/hotfix/base-unchanged.json /tmp/hotfix/new-unchanged.json" in behaviour
    assert "assert base and not any(base.values())" in behaviour
    assert "all(new.values())" in behaviour
    replay = _step(order[2])["run"]
    assert '"$MERGE_833^1" "$MERGE_833"' in replay
    assert '"apps/api/app/routers/v1/oauth_provider.py "' in replay


def test_merge_is_janua_833_and_touches_only_the_shipped_file():
    merge = WORKFLOW["env"]["MERGE_833"]
    subject = _git("log", "-1", "--format=%s", merge).decode()
    assert "(#833)" in subject, subject
    touched = set(
        _git("diff", "--name-only", f"{merge}^1", merge, "--", "apps/api/app").decode().split()
    )
    assert touched == {PROD_PATH}


def test_the_changed_file_differs_from_production_by_exactly_the_reviewed_hunks():
    """Computed with the same `git diff --no-index -U3` the workflow runs (diff(1)
    groups hunks differently on Mac and Linux), bytes end to end."""
    with tempfile.NamedTemporaryFile("wb", suffix=".py") as handle:
        handle.write(_production_copy())
        handle.flush()
        out = subprocess.run(
            ["git", "diff", "--no-index", "--no-color", "-U3", handle.name, str(SHIPPED)],
            capture_output=True,
        ).stdout
    assert out[out.index(b"@@") :] == (HOTFIX / "oauth_provider.diff").read_bytes()


def test_shipped_file_is_production_copy_plus_the_merge():
    """The replay the workflow runs: production's copy plus the merge's own diff
    is exactly the shipped file, so no hunk outside janua#833 travels (main's
    oauth_provider.py also carries janua#792 and janua#801)."""
    merge = WORKFLOW["env"]["MERGE_833"]
    with tempfile.TemporaryDirectory() as tmp:
        replay = Path(tmp)
        target = replay / PROD_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_production_copy())
        patch = _git("diff", "--no-color", f"{merge}^1", merge, "--", "apps/api/app")
        subprocess.run(
            ["git", "apply", "-"], cwd=replay, input=patch, check=True, capture_output=True
        )
        assert target.read_bytes() == SHIPPED.read_bytes()
    # oauth_provider.py is not main's.
    assert SHIPPED.read_bytes() != (ROOT / PROD_PATH).read_bytes()


def test_check_script_passes_in_this_checkout():
    """The script the workflow runs in the built image, run here: on this
    checkout every property janua#833 adds holds, and the predicates every
    client already went through trust exactly the confidential first-party
    shapes they trusted before (never a public client)."""
    report = _check_output()
    assert report["SILENT"] and all(report["SILENT"].values()), report["SILENT"]
    trusted = {
        name
        for name, (silent, preconsented) in report["UNCHANGED"].items()
        if silent or preconsented
    }
    assert trusted == {"active-confidential-marked", "active-confidential-first-party-name"}
    assert all(silent == preconsented for silent, preconsented in report["UNCHANGED"].values())
    assert len(report["UNCHANGED"]) == 12


def test_exception_record_names_the_owner_go_and_its_scope():
    approved = _record("Approved by")
    assert "2026-11-18" in approved
    assert "promote-to-prod.yml` stays held" in approved
    assert "this hotfix only (janua#833)" in approved
    assert WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1] in _record("Replaces")


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard
