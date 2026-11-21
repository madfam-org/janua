"""The edge-hardening hotfix stays exactly as wide as it was reviewed.

deployment/hotfix/janua-api-edge-hardening builds the image production runs
(row 13) plus the nine merges after it (janua#844, #845, #846, #847, #848, #850,
#851, #852, #853), because the promotion hold
(scripts/staging/promotion_runtime_guard.py) blocks normal promotions. The
image's application code is apps/api/app at SOURCE, except seven files that keep
production's copies (kept_files.txt) and oauth_provider_shared.py, which ships
from the folder without janua#801's `roles` filter. These tests keep the
Dockerfile, the manifests and the workflow from quietly widening, pin the one
reviewed hunk of the shipped module, and run the behaviour check the workflow
runs in the built image.

Everything is read from SOURCE (git), not from this checkout: later merges move
main past what this image ships, and the workflow refuses to build then.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import runpy
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-edge-hardening"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-edge-hardening.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
ENV = WORKFLOW["env"]
PREVIOUS_WORKFLOW = yaml.safe_load(
    (ROOT / ".github/workflows/hotfix-janua-api-login-double-submit.yml").read_text()
)
PREVIOUS_README = ROOT / "deployment/hotfix/janua-api-login-double-submit/README.md"
SHARED = "apps/api/app/routers/v1/oauth_provider_shared.py"
NINE = ("#844", "#845", "#846", "#847", "#848", "#850", "#851", "#852", "#853")
ADDED_ROUTES = {
    "GET /api/v1/auth/error",
    "GET /api/v1/auth/reset-password/done",
    "POST /api/v1/internal/users/change-email",
}
BASE_STEP = "Base image is BASE_SOURCE plus the earlier hotfix files"
ORDER = [
    BASE_STEP,
    "The shipped tree is SOURCE, and SOURCE is row 13 plus the nine merges",
    "oauth_provider_shared.py.shipped is SOURCE's minus janua#801's roles filter",
    "Build and push",
    "Hotfix is SOURCE's application code with the kept files and the shipped module",
    "Discovery, client policy and hosted pages unchanged; refused navigations get the page; "
    "routes are the base's plus three",
    "Sign image with cosign",
]


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def _kept() -> list[str]:
    return (HOTFIX / "kept_files.txt").read_text().split()


def _shipped_manifest() -> list[tuple[str, str]]:
    rows = [line.split(" ", 1) for line in (HOTFIX / "shipped_files.txt").read_text().splitlines()]
    return [(status, path) for status, path in rows]


def _instructions() -> list[str]:
    lines = DOCKERFILE.read_text().splitlines()
    return [line for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _steps() -> list[dict]:
    return WORKFLOW["jobs"]["build"]["steps"]


def _step(name: str) -> dict:
    return next(s for s in _steps() if s.get("name") == name)


def _record(field: str, readme: Path = HOTFIX / "README.md") -> str:
    row = re.search(rf"^\| {re.escape(field)} \| (.+) \|$", readme.read_text(), re.M)
    assert row, f"{readme} exception record has no {field!r} row"
    return row.group(1)


def test_dockerfile_is_the_base_the_source_tree_the_kept_files_and_the_module():
    base, tree, *rest = _instructions()
    image = ENV["BASE_IMAGE"]
    assert base == f"FROM {image}"
    assert re.fullmatch(r"ghcr\.io/madfam-org/janua-api@sha256:[0-9a-f]{64}", image)
    assert tree == "COPY --chown=janua:python apps/api/app/ /app/app/"
    kept, module = rest[:-1], rest[-1]
    assert kept == [
        f"COPY --chown=janua:python --from={image} /app/app/{f} /app/app/{f}" for f in _kept()
    ]
    assert module == (
        "COPY --chown=janua:python deployment/hotfix/janua-api-edge-hardening/"
        "oauth_provider_shared.py.shipped /app/app/routers/v1/oauth_provider_shared.py"
    )
    assert len(_kept()) == 7 and len(set(_kept())) == 7


def test_base_is_the_image_production_pins():
    """Before the pin PR, production runs the base; after it, production runs the
    hotfix digest the exception record names (or a later hotfix reached from it
    through the exception records)."""
    digest = ENV["BASE_IMAGE"].split("@", 1)[1]
    kustomization = (ROOT / "k8s/overlays/production/kustomization.yaml").read_text()
    block = re.search(r"name: ghcr\.io/madfam-org/janua-api\n(?:\s+\S.*\n){1,3}", kustomization)
    assert block, "production overlay has no janua-api image"
    if digest in block.group(0):
        return
    pinned = re.search(r"sha256:[0-9a-f]{64}", _record("Hotfix digest"))
    assert pinned, "the base is not the production pin and this record names no hotfix digest"
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
        assert current in successors and current not in seen
        seen.add(current)
        current = successors[current]


def test_base_is_row_13_with_its_proven_sources():
    digest = ENV["BASE_IMAGE"].split("@", 1)[1]
    assert re.search(rf"^\| Hotfix digest \| `{digest}`", PREVIOUS_README.read_text(), re.M)
    previous = PREVIOUS_WORKFLOW["env"]
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
        "SILENT_SOURCE",
        "PRIMARY_DIR",
        "HOSTED_DIR",
        "SILENT_DIR",
        "POLICY_DUMP",
    ):
        assert ENV[key] == previous[key], key
    assert ENV["DOUBLE_SUBMIT_DIR"] == previous["HOTFIX_DIR"]
    assert ENV["DOUBLE_SUBMIT_CHECK"] == previous["CHECK"]
    built = re.search(r"`main` `([0-9a-f]{7,40})`", _record("Built by", PREVIOUS_README))
    assert built and ENV["DOUBLE_SUBMIT_SOURCE"].startswith(built.group(1))
    assert re.fullmatch(r"[0-9a-f]{40}", ENV["DOUBLE_SUBMIT_SOURCE"])
    run = _step(BASE_STEP)["run"]
    previous_run = next(
        s for s in PREVIOUS_WORKFLOW["jobs"]["build"]["steps"] if s.get("name") == BASE_STEP
    )["run"]
    # Every overlay row 13 proved is proved again, in the same order, then row 13's.
    lines = [
        line.strip()
        for line in previous_run.splitlines()
        if "git show" in line or line.strip().startswith("for f in")
    ]
    positions = [run.index(line) for line in lines]
    assert positions == sorted(positions)
    row_13 = 'git show "$DOUBLE_SUBMIT_SOURCE:apps/api/app/$f" > "/tmp/hotfix/src/apps/api/app/$f"'
    assert positions[-1] < run.index(row_13) < run.index("diff -r -x __pycache__")
    assert (
        "for f in auth/hosted_locale.py auth/tenant_login_context.py routers/v1/auth.py; do"
        in run[run.index('"$SILENT_SOURCE:$SILENT_DIR') :]
    )
    for key in ("POLICY_DUMP", "CHECK", "DOUBLE_SUBMIT_CHECK", "DOCKERFILE"):
        assert (ROOT / ENV[key]).is_file(), key
    assert ENV["DOCKERFILE"] == str(DOCKERFILE.relative_to(ROOT))
    assert ENV["HOTFIX_DIR"] == str(HOTFIX.relative_to(ROOT))


def test_source_is_row_13_plus_exactly_the_nine_merges():
    source = ENV["SOURCE"]
    assert re.fullmatch(r"[0-9a-f]{40}", source)
    assert "(#852)" in _git("log", "-1", "--format=%s", source).decode()
    subjects = _git(
        "log", "--format=%s", f"{ENV['DOUBLE_SUBMIT_SOURCE']}..{source}", "--", "apps/api/app"
    ).decode()
    numbers = sorted(re.findall(r"\((#\d+)\)$", subjects, re.M))
    assert numbers == sorted(NINE), subjects


def test_shipped_files_are_what_the_nine_merges_change():
    """Production's copy of every file the nine merges touch is row 13's source's
    (the earlier differences, (b) and (c) in the README, travel inside files the
    merges modify anyway), so the manifest is the merges' own name-status."""
    status = _git(
        "diff",
        "--name-status",
        "--no-renames",
        ENV["DOUBLE_SUBMIT_SOURCE"],
        ENV["SOURCE"],
        "--",
        "apps/api/app",
    ).decode()
    rows = [line.split("\t") for line in status.splitlines()]
    expected = sorted(
        ((s, p.removeprefix("apps/api/app/")) for s, p in rows), key=lambda row: row[1]
    )
    assert _shipped_manifest() == expected
    assert {s for s, _ in expected} == {"A", "M"}
    assert sum(1 for s, _ in expected if s == "A") == 30
    assert sum(1 for s, _ in expected if s == "M") == 10


def test_kept_files_are_unshipped_main_changes_the_nine_merges_never_touched():
    shipped = {path for _, path in _shipped_manifest()}
    dockerfiles = "\n".join(
        p.read_text() for p in (ROOT / "deployment/hotfix").glob("*/Dockerfile") if p != DOCKERFILE
    )
    for f in _kept():
        path = f"apps/api/app/{f}"
        assert f not in shipped, f
        assert path not in dockerfiles, f"{f} was shipped by an earlier row"
        # Changed on main since the base promotion, never by the nine merges.
        assert _git("show", f"{ENV['BASE_SOURCE']}:{path}") != _git(
            "show", f"{ENV['SOURCE']}:{path}"
        )
        assert not _git(
            "diff", "--name-only", ENV["DOUBLE_SUBMIT_SOURCE"], ENV["SOURCE"], "--", path
        )


def test_shipped_module_differs_from_source_by_exactly_the_reviewed_hunk():
    with tempfile.TemporaryDirectory() as tmp:
        source_copy = Path(tmp) / "source.py"
        source_copy.write_bytes(_git("show", f"{ENV['SOURCE']}:{SHARED}"))
        out = subprocess.run(
            [
                "git",
                "diff",
                "--no-index",
                "--no-color",
                "-U3",
                str(source_copy),
                str(HOTFIX / "oauth_provider_shared.py.shipped"),
            ],
            capture_output=True,
        ).stdout
    assert out[out.index(b"@@") :] == (HOTFIX / "oauth_provider_shared.diff").read_bytes()


def test_the_hunk_is_production_roles_collection_instead_of_janua_801s_filter():
    diff = (HOTFIX / "oauth_provider_shared.diff").read_text().splitlines()
    removed = [line[1:].strip() for line in diff if line.startswith("-")]
    added = [line[1:].strip() for line in diff if line.startswith("+")]
    assert diff[0].startswith("@@") and sum(1 for line in diff if line.startswith("@@")) == 1
    assert 'entitlements["roles"] = organization_roles_for_roles_claim(' in removed
    assert added == [
        "# Collect all roles across active organizations",
        "roles = list({m.role for m in memberships if m.role})",
        'entitlements["roles"] = roles',
    ]
    # Exactly production's lines: the copy of oauth_provider.py production runs.
    production = _git(
        "show", f"{ENV['SILENT_SOURCE']}:{ENV['SILENT_DIR']}/oauth_provider.py.shipped"
    ).decode()
    block = "\n".join(line[1:] for line in diff if line.startswith("+"))
    assert block in production
    shipped = (HOTFIX / "oauth_provider_shared.py.shipped").read_text()
    assert "organization_roles_for_roles_claim(" not in shipped


def test_workflow_is_manual_and_from_main_only():
    triggers = WORKFLOW.get("on", WORKFLOW.get(True))  # PyYAML reads `on` as True
    assert set(triggers) == {"workflow_dispatch"}
    first = _steps()[0]
    assert first["if"] == "github.ref != 'refs/heads/main'"
    assert "exit 1" in first["run"]
    assert WORKFLOW["concurrency"] == {
        "group": "hotfix-janua-api-edge-hardening",
        "cancel-in-progress": False,
    }


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
    assert _step("Build and push")["with"]["tags"] == (
        "${{ env.TARGET }}:hotfix-edge-hardening-${{ github.sha }}"
    )


def test_workflow_proves_source_delta_image_and_behaviour_before_signing():
    names = [step.get("name", "") for step in _steps()]
    positions = [names.index(name) for name in ORDER]
    assert positions == sorted(positions), names
    tree = _step(ORDER[1])["run"]
    assert 'git diff --quiet "$SOURCE" HEAD -- apps/api/app' in tree
    assert '"(#844) (#845) (#846) (#847) (#848) (#850) (#851) (#852) (#853) "' in tree
    assert 'diff /tmp/hotfix/source-delta.txt "$HOTFIX_DIR/shipped_files.txt"' in tree
    module = _step(ORDER[2])["run"]
    assert (
        'cmp /tmp/hotfix/oauth_provider_shared.diff "$HOTFIX_DIR/oauth_provider_shared.diff"'
        in module
    )
    image = _step(ORDER[4])["run"]
    assert "base_layers + 9" in image
    assert "diff -r -x __pycache__ /tmp/hotfix/expected/app /tmp/hotfix/new/app" in image
    assert "diff -r -x __pycache__ /tmp/hotfix/base/versions /tmp/hotfix/new/versions" in image
    behaviour = _step(ORDER[5])["run"]
    for line in (
        "cmp /tmp/hotfix/base-metadata.json /tmp/hotfix/new-metadata.json",
        "cmp /tmp/hotfix/base-policy.json /tmp/hotfix/new-policy.json",
        "cmp /tmp/hotfix/base-eh-UNCHANGED.json /tmp/hotfix/new-eh-UNCHANGED.json",
        'assert differing in ([], ["auth_routes"]), differing',
        "assert len(pages) == 7 and all(pages.values()), pages",
        "assert base_fix and not any(base_fix.values()), base_fix",
        "assert new_routes == base_routes | added",
    ):
        assert line in behaviour, line
    for route in ADDED_ROUTES:
        assert f'"{route}"' in behaviour, route
    assert '"$DOUBLE_SUBMIT_DIR/pages" > /tmp/hotfix/double-submit-check.py' in behaviour


def _check_output() -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        runpy.run_path(str(HOTFIX / "check_edge_hardening.py"))
    lines = out.getvalue().splitlines()
    return {
        key: json.loads(next(r for r in lines if r.startswith(key + "=")).removeprefix(key + "="))
        for key in ("ROUTES", "UNCHANGED", "FIX")
    }


def test_check_script_passes_in_this_checkout():
    """The script the workflow runs in both images, run here: every property this
    row adds holds; an API caller on a hosted route keeps its JSON envelope; the
    three new routes are registered."""
    report = _check_output()
    assert report["FIX"] and all(report["FIX"].values()), report["FIX"]
    assert len(report["FIX"]) == 6
    assert ADDED_ROUTES <= set(report["ROUTES"])
    for name, answer in report["UNCHANGED"].items():
        if name.endswith("_rate_limited_429") and answer == {"raised": "AttributeError"}:
            # tests/conftest.py replaces slowapi's Limiter with a stub that has no
            # _inject_headers, so slowapi's own JSON answer cannot be built in this
            # process; in the images (real slowapi) the workflow compares it.
            continue
        assert answer.get("media_type") == "application/json", (name, answer)
        assert answer.get("location") is None, (name, answer)
    assert report["UNCHANGED"]["api_caller_http_400"]["status"] == 400


def test_readme_names_what_travels_and_what_stays():
    readme = (HOTFIX / "README.md").read_text()
    for number in NINE:
        assert f"janua{number}" in readme, number
    for f in _kept():
        assert f"`{f}`" in readme, f
    assert "carried along" in readme.lower()
    index = (ROOT / "deployment/hotfix/README.md").read_text()
    assert "[`janua-api-edge-hardening`](janua-api-edge-hardening/README.md)" in index


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard
