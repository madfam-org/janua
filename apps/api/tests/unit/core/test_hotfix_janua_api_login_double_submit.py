"""The login-double-submit hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-login-double-submit builds the image production runs
plus janua#841 (a second sign-in POST for an already-used pending request lands
in the application or on a GET «expired» page instead of the raw JSON error
body; hosted forms load a same-origin one-press script), because the promotion
hold (scripts/staging/promotion_runtime_guard.py) blocks normal promotions.
These tests keep the Dockerfile and its workflow from quietly widening, pin that
each shipped file differs from production's copy by exactly the reviewed hunks
(and is production's copy plus the merge, nothing else), and run the behaviour
check the workflow runs in the built image.

The replay tests refuse a MERGE_841 that is not a full commit id, so the
folder cannot be built against a placeholder.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-login-double-submit"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-login-double-submit.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
SILENT_WORKFLOW = yaml.safe_load(
    (ROOT / ".github/workflows/hotfix-janua-api-public-silent-auth.yml").read_text()
)
COPIED = {
    "apps/api/app/auth/hosted_locale.py": "/app/app/auth/",
    "apps/api/app/auth/tenant_login_context.py": "/app/app/auth/",
    "apps/api/app/routers/v1/auth.py": "/app/app/routers/v1/",
}
# (where production's copy comes from, the file the image gets, the reviewed hunks)
HUNKS = [
    ("HOSTED_SOURCE", "apps/api/app/auth/hosted_locale.py", "hosted_locale.diff"),
    ("ORG_LOGIN_SOURCE", "apps/api/app/auth/tenant_login_context.py", "tenant_login_context.diff"),
    ("HOSTED_SOURCE", "apps/api/app/routers/v1/auth.py", "auth.diff"),
]
PLACEHOLDER = "MERGE_841_PENDING"


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def _production_copy(source_key: str, path: str) -> bytes:
    return _git("show", f"{WORKFLOW['env'][source_key]}:{path}")


def _shipped(path: str) -> bytes:
    """The bytes the image gets for one copied file.

    Until the image is built (the exception record's Built by row is pending),
    that is this checkout's copy, which the workflow COPYs from main. Once the
    record names the `main` commit the image was built from, it is that commit's
    copy: later merges move main past what this image ships, exactly as the next
    row's workflow will replay this row from that commit.
    """
    built = re.search(r"`main` `([0-9a-f]{7,40})`", _record("Built by"))
    if built:
        return _git("show", f"{built.group(1)}:{path}")
    return (ROOT / path).read_bytes()


def _merge() -> str:
    merge = WORKFLOW["env"]["MERGE_841"]
    if merge == PLACEHOLDER or not re.fullmatch(r"[0-9a-f]{40}", merge):
        pytest.fail(
            f"MERGE_841 is {merge!r}: write janua#841's squash-merge commit into "
            f"{WORKFLOW_PATH.relative_to(ROOT)} before this hotfix is merged or built."
        )
    return merge


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
        runpy.run_path(str(HOTFIX / "check_double_submit.py"))
    lines = out.getvalue().splitlines()
    return {
        key: json.loads(
            next(row for row in lines if row.startswith(key + "=")).removeprefix(key + "=")
        )
        for key in ("UNCHANGED", "FIX")
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


def test_base_is_the_public_silent_auth_hotfix_with_its_proven_sources():
    readme = (ROOT / "deployment/hotfix/janua-api-public-silent-auth/README.md").read_text()
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
        "HOSTED_SOURCE",
        "PRIMARY_DIR",
        "HOSTED_DIR",
        "POLICY_DUMP",
    ):
        assert WORKFLOW["env"][key] == SILENT_WORKFLOW["env"][key], key
    assert WORKFLOW["env"]["SILENT_DIR"] == SILENT_WORKFLOW["env"]["HOTFIX_DIR"]
    built = re.search(r"^\| Built by \| .*`main` `([0-9a-f]{7,40})`", readme, re.M)
    assert built and WORKFLOW["env"]["SILENT_SOURCE"].startswith(built.group(1))
    assert re.fullmatch(r"[0-9a-f]{40}", WORKFLOW["env"]["SILENT_SOURCE"])
    name = "Base image is BASE_SOURCE plus the earlier hotfix files"
    base_step = _step(name)
    silent_base = next(
        s for s in SILENT_WORKFLOW["jobs"]["build"]["steps"] if s.get("name") == name
    )
    # Every overlay the silent-auth hotfix proved is proved again, plus its own file.
    for line in silent_base["run"].splitlines():
        if "git show" in line or line.strip().startswith("for f in"):
            assert line.strip() in base_step["run"], line
    silent_line = (
        'git show "$SILENT_SOURCE:$SILENT_DIR/oauth_provider.py.shipped" > '
        "/tmp/hotfix/src/apps/api/app/routers/v1/oauth_provider.py"
    )
    assert silent_line in base_step["run"]
    # The silent-auth overlay comes after the hosted-locale overlay it supersedes,
    # and before the comparison with the running image.
    run = base_step["run"]
    assert run.index(silent_line) > run.index('"$HOSTED_SOURCE:$HOSTED_DIR/oauth_provider.py.shipped"')
    assert run.index(silent_line) < run.index("diff -r -x __pycache__")
    assert WORKFLOW["env"]["DOCKERFILE"] == str(DOCKERFILE.relative_to(ROOT))
    assert WORKFLOW["env"]["HOTFIX_DIR"] == str(HOTFIX.relative_to(ROOT))
    assert (ROOT / WORKFLOW["env"]["POLICY_DUMP"]).is_file()
    assert (ROOT / WORKFLOW["env"]["CHECK"]).is_file()


def test_production_copies_are_the_last_rows_that_shipped_them():
    """hosted_locale.py and auth.py were last shipped by the hosted-locale hotfix
    (row 11, built from HOSTED_SOURCE) and tenant_login_context.py by the
    org-bound-login hotfix (row 3, ORG_LOGIN_SOURCE); no later row touched them,
    so those copies are what production runs."""
    hosted = (ROOT / "deployment/hotfix/janua-api-hosted-locale/Dockerfile").read_text()
    org = (ROOT / "deployment/hotfix/janua-api-org-bound-login/Dockerfile").read_text()
    assert "apps/api/app/auth/hosted_locale.py" in hosted
    assert "apps/api/app/routers/v1/auth.py" in hosted
    assert "apps/api/app/auth/tenant_login_context.py" in org
    later = [
        ROOT / f"deployment/hotfix/{name}/Dockerfile"
        for name in (
            "janua-api-org-role-shape",
            "janua-api-entitlement-source",
            "janua-api-json-encoding",
            "janua-api-webhooks",
            "janua-api-primary-organization",
            "janua-api-contain-roles-guest",
            "janua-api-public-silent-auth",
        )
    ]
    for dockerfile in later:
        text = dockerfile.read_text()
        for path in COPIED:
            assert path.removeprefix("apps/api/") not in text, (dockerfile, path)
    reservations = (ROOT / "deployment/hotfix/janua-api-reservations-2/Dockerfile").read_text()
    assert "tenant_login_context.py" not in reservations


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


def test_workflow_expects_exactly_the_three_files():
    step = _step("Hotfix differs from the base by three files")
    for changed in ("auth/hosted_locale.py", "auth/tenant_login_context.py", "routers/v1/auth.py"):
        assert f"/tmp/hotfix/base/app/{changed} and /tmp/hotfix/new/app/{changed} differ" in step["run"]
        assert f"cmp /tmp/hotfix/new/app/{changed} apps/api/app/{changed}" in step["run"]
    assert step["run"].count(" differ\"") == 3
    assert "base_layers + 3" in step["run"]
    assert "Only in" not in step["run"]
    assert _step("Build and push")["with"]["tags"] == (
        "${{ env.TARGET }}:hotfix-login-double-submit-${{ github.sha }}"
    )


def test_workflow_checks_source_delta_and_behaviour_before_signing():
    names = [step.get("name", "") for step in _steps()]
    order = [
        "Base image is BASE_SOURCE plus the earlier hotfix files",
        "The changed files differ from production's only by the reviewed hunks",
        "The shipped files are production's copies plus janua#841",
        "Build and push",
        "Hotfix differs from the base by three files",
        "Discovery, client policy and hosted pages unchanged; a used sign-in request answers with a page",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names
    hunks = _step(order[1])["run"]
    for _, path, diff_name in HUNKS:
        assert f"check {path.removeprefix('apps/api/app/')} {diff_name}" in hunks
    behaviour = _step(order[5])["run"]
    assert "cmp /tmp/hotfix/base-metadata.json /tmp/hotfix/new-metadata.json" in behaviour
    assert "cmp /tmp/hotfix/base-policy.json /tmp/hotfix/new-policy.json" in behaviour
    assert "cmp /tmp/hotfix/base-unchanged.json /tmp/hotfix/new-unchanged.json" in behaviour
    assert "grep '^FIX='" in behaviour
    assert "assert base and not any(base.values())" in behaviour
    assert "all(new.values())" in behaviour
    replay = _step(order[2])["run"]
    assert 'if [[ ! "$MERGE_841" =~ ^[0-9a-f]{40}$ ]]; then' in replay
    assert '"$MERGE_841^1" "$MERGE_841"' in replay
    assert (
        '"apps/api/app/auth/hosted_locale.py apps/api/app/auth/tenant_login_context.py '
        'apps/api/app/routers/v1/auth.py "'
    ) in replay


def test_merge_is_janua_841_and_touches_only_the_shipped_files():
    merge = _merge()
    subject = _git("log", "-1", "--format=%s", merge).decode()
    assert "(#841)" in subject, subject
    touched = set(
        _git("diff", "--name-only", f"{merge}^1", merge, "--", "apps/api/app").decode().split()
    )
    assert touched == set(COPIED)


def test_the_changed_files_differ_from_production_by_exactly_the_reviewed_hunks():
    """Computed with the same `git diff --no-index -U3` the workflow runs (diff(1)
    groups hunks differently on Mac and Linux), bytes end to end."""
    for source_key, path, diff_name in HUNKS:
        with tempfile.TemporaryDirectory() as tmp:
            prod_copy, image_copy = Path(tmp) / "prod.py", Path(tmp) / "image.py"
            prod_copy.write_bytes(_production_copy(source_key, path))
            image_copy.write_bytes(_shipped(path))
            out = subprocess.run(
                ["git", "diff", "--no-index", "--no-color", "-U3", str(prod_copy), str(image_copy)],
                capture_output=True,
            ).stdout
        assert out[out.index(b"@@") :] == (HOTFIX / diff_name).read_bytes(), diff_name


def test_shipped_files_are_production_copies_plus_the_merge():
    """The replay the workflow runs: production's copies plus the merge's own
    diff are exactly the shipped files, so no hunk outside janua#841 travels."""
    merge = _merge()
    with tempfile.TemporaryDirectory() as tmp:
        replay = Path(tmp)
        for source_key, path, _ in HUNKS:
            target = replay / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(_production_copy(source_key, path))
        patch = _git("diff", "--no-color", f"{merge}^1", merge, "--", "apps/api/app")
        subprocess.run(
            ["git", "apply", "-"], cwd=replay, input=patch, check=True, capture_output=True
        )
        for _, path, _ in HUNKS:
            assert (replay / path).read_bytes() == _shipped(path), path


def test_check_script_passes_in_this_checkout():
    """The script the workflow runs in the built image, run here: on this
    checkout every property janua#841 adds holds, and the password page with
    janua#841's two insertions removed is the golden production's source
    rendered (so equal UNCHANGED hashes across the images mean production's
    page, byte for byte)."""
    report = _check_output()
    assert report["FIX"] and all(report["FIX"].values()), report["FIX"]
    golden = ROOT / "apps/api/tests/unit/routers/fixtures/hosted_login_unlisted"
    for locale in ("en", "es"):
        expected = hashlib.sha256((golden / f"{locale}.html").read_bytes()).hexdigest()
        assert report["UNCHANGED"][f"login_page_password_{locale}"] == expected, locale
    assert report["UNCHANGED"]["gone_request_answer"] == [
        400,
        "La solicitud de acceso venció. Vuelve al MAP para iniciar.",
    ]
    assert len(report["FIX"]) == 9


def test_exception_record_names_the_owner_request_and_its_scope():
    approved = _record("Approved by")
    assert "2026-11-19" in approved
    assert "Reason: production incident 2026-11-19." in approved
    assert "The pin needs the owner's explicit OK" in approved
    assert "promote-to-prod.yml` stays held" in approved
    assert "this hotfix only (janua#841)" in approved
    assert WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1] in _record("Replaces")


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard
