"""The hosted-locale hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-hosted-locale builds the image production runs plus
janua#814 and janua#820, because the promotion hold
(scripts/staging/promotion_runtime_guard.py) blocks normal promotions. These
tests keep the Dockerfile and its workflow from quietly widening, pin that the
shipped files differ from production's copies by exactly the reviewed hunks
(and are production's copies plus the two merges, nothing else), and run the
behaviour check the workflow runs in the built image.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-hosted-locale"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-hosted-locale.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
CONTAIN_WORKFLOW = yaml.safe_load(
    (ROOT / ".github/workflows/hotfix-janua-api-contain-roles-guest.yml").read_text()
)
COPIED = {
    "apps/api/app/auth/hosted_locale.py": "/app/app/auth/",
    "apps/api/app/routers/v1/auth.py": "/app/app/routers/v1/",
    "deployment/hotfix/janua-api-hosted-locale/oauth_provider.py": "/app/app/routers/v1/",
}
# (production's copy as `source key:path`, the file the image gets, the reviewed hunk)
HUNKS = [
    ("RES2_SOURCE", "apps/api/app/auth/hosted_locale.py",
     ROOT / "apps/api/app/auth/hosted_locale.py", "hosted_locale.diff"),
    ("RES2_SOURCE", "apps/api/app/routers/v1/auth.py",
     ROOT / "apps/api/app/routers/v1/auth.py", "auth.diff"),
    ("BASE_SOURCE", "apps/api/app/routers/v1/oauth_provider.py",
     HOTFIX / "oauth_provider.py", "oauth_provider.diff"),
]


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


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
        runpy.run_path(str(HOTFIX / "check_locale.py"))
    lines = out.getvalue().splitlines()
    return {
        key: json.loads(next(row for row in lines if row.startswith(key + "=")).removeprefix(key + "="))
        for key in ("LOCALE", "ENGLISH")
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


def test_base_is_the_contain_roles_guest_hotfix_with_its_proven_sources():
    readme = (ROOT / "deployment/hotfix/janua-api-contain-roles-guest/README.md").read_text()
    digest = WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1]
    assert re.search(rf"^\| Hotfix digest \| `{digest}`", readme, re.M)
    for key in (
        "BASE_SOURCE", "RESERVED_SOURCE", "CHATGPT_SOURCE", "ORG_LOGIN_SOURCE", "ROLE_SHAPE_SOURCE",
        "ENTITLEMENT_SOURCE", "RES2_SOURCE", "JSONENC_SOURCE", "WEBHOOKS_SOURCE", "PRIMARY_SOURCE",
        "PRIMARY_DIR", "POLICY_DUMP",
    ):
        assert WORKFLOW["env"][key] == CONTAIN_WORKFLOW["env"][key], key
    built = re.search(r"^\| Built by \| .*`main` `([0-9a-f]{7,40})`", readme, re.M)
    assert built and WORKFLOW["env"]["CONTAIN_SOURCE"].startswith(built.group(1))
    name = "Base image is BASE_SOURCE plus the earlier hotfix files"
    base_step = _step(name)
    contain_base = next(s for s in CONTAIN_WORKFLOW["jobs"]["build"]["steps"] if s.get("name") == name)
    # Every overlay the contain-roles-guest hotfix proved is proved again, plus its own files.
    for line in contain_base["run"].splitlines():
        if "git show" in line or line.strip().startswith("for f in"):
            assert line.strip() in base_step["run"], line
    assert "for f in core/reserved_oauth_boundaries.py routers/v1/guest.py; do" in base_step["run"]
    assert '"$CONTAIN_SOURCE:apps/api/app/$f"' in base_step["run"]
    # The contain overlay comes after the reservations-2 overlay it supersedes.
    assert base_step["run"].index("$CONTAIN_SOURCE") > base_step["run"].index("$RES2_SOURCE")
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


def test_workflow_expects_exactly_the_three_files():
    step = _step("Hotfix differs from the base by three files")
    for changed in ("auth/hosted_locale.py", "routers/v1/auth.py", "routers/v1/oauth_provider.py"):
        assert f"/tmp/hotfix/base/app/{changed} and /tmp/hotfix/new/app/{changed} differ" in step["run"]
    assert "cmp /tmp/hotfix/new/app/auth/hosted_locale.py apps/api/app/auth/hosted_locale.py" in step["run"]
    assert "cmp /tmp/hotfix/new/app/routers/v1/auth.py apps/api/app/routers/v1/auth.py" in step["run"]
    assert 'cmp /tmp/hotfix/new/app/routers/v1/oauth_provider.py "$HOTFIX_DIR/oauth_provider.py"' in step["run"]
    assert "base_layers + 3" in step["run"]
    assert "Only in" not in step["run"]


def test_workflow_checks_source_delta_and_behaviour_before_signing():
    names = [step.get("name", "") for step in _steps()]
    order = [
        "Base image is BASE_SOURCE plus the earlier hotfix files",
        "The changed files differ from production's only by the reviewed hunks",
        "The shipped files are production's copies plus janua#814 and janua#820",
        "Build and push",
        "Hotfix differs from the base by three files",
        "Discovery, client policy and English pages unchanged; chooser and refusal speak Spanish when asked",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names
    behaviour = _step(order[5])["run"]
    assert "cmp /tmp/hotfix/base-english.json /tmp/hotfix/new-english.json" in behaviour
    assert "assert base and not any(base.values())" in behaviour
    assert "all(new.values())" in behaviour
    replay = _step(order[2])["run"]
    assert '"$MERGE_814^1" "$MERGE_814"' in replay and '"$MERGE_820^1" "$MERGE_820"' in replay


def test_merges_are_janua_814_and_820_and_touch_only_the_shipped_files():
    for key, number in (("MERGE_814", "#814"), ("MERGE_820", "#820")):
        subject = _git("log", "-1", "--format=%s", WORKFLOW["env"][key]).decode()
        assert f"({number})" in subject, subject
    touched = {
        key: set(_git("diff", "--name-only", f"{WORKFLOW['env'][key]}^1", WORKFLOW["env"][key],
                      "--", "apps/api/app").decode().split())
        for key in ("MERGE_814", "MERGE_820")
    }
    assert touched["MERGE_814"] == {"apps/api/app/auth/hosted_locale.py", "apps/api/app/routers/v1/oauth_provider.py"}
    assert touched["MERGE_820"] == {
        "apps/api/app/auth/hosted_locale.py",
        "apps/api/app/routers/v1/auth.py",
        "apps/api/app/routers/v1/oauth_provider.py",
    }


def test_the_changed_files_differ_from_production_by_exactly_the_reviewed_hunks():
    """Computed with the same `git diff --no-index -U3` the workflow runs (diff(1)
    groups hunks differently on Mac and Linux), bytes end to end."""
    for source_key, prod_path, image_file, diff_name in HUNKS:
        base = _git("show", f"{WORKFLOW['env'][source_key]}:{prod_path}")
        with tempfile.NamedTemporaryFile("wb", suffix=".py") as handle:
            handle.write(base)
            handle.flush()
            out = subprocess.run(
                ["git", "diff", "--no-index", "--no-color", "-U3", handle.name, str(image_file)],
                capture_output=True,
            ).stdout
        assert out[out.index(b"@@"):] == (HOTFIX / diff_name).read_bytes(), diff_name


def test_shipped_files_are_production_copies_plus_the_two_merges():
    """The replay the workflow runs: production's copies plus the merges' own
    diffs are exactly the shipped files, so no hunk outside janua#814 and
    janua#820 travels (main's oauth_provider.py also carries janua#792 and #801)."""
    with tempfile.TemporaryDirectory() as tmp:
        replay = Path(tmp)
        for source_key, prod_path, _, _ in HUNKS:
            target = replay / prod_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(_git("show", f"{WORKFLOW['env'][source_key]}:{prod_path}"))
        for key in ("MERGE_814", "MERGE_820"):
            patch = _git("diff", "--no-color", f"{WORKFLOW['env'][key]}^1", WORKFLOW["env"][key], "--", "apps/api/app")
            subprocess.run(["git", "apply", "-"], cwd=replay, input=patch, check=True, capture_output=True)
        for _, prod_path, image_file, _ in HUNKS:
            assert (replay / prod_path).read_bytes() == image_file.read_bytes(), prod_path
    # The two files copied from main are main's; oauth_provider.py is not main's.
    assert (HOTFIX / "oauth_provider.py").read_bytes() != (ROOT / "apps/api/app/routers/v1/oauth_provider.py").read_bytes()


def test_check_script_passes_in_this_checkout():
    """The script the workflow runs in the built image, run here: on this
    checkout every language property it reports must hold."""
    report = _check_output()
    assert report["LOCALE"] and all(report["LOCALE"].values()), report["LOCALE"]
    assert set(report["ENGLISH"]) == {
        "chooser_named", "chooser_unnamed",
        "refusal_switch_refused_cross_origin", "refusal_switch_refused_not_held",
    }


def test_english_pages_match_the_goldens_production_rendered():
    """The English pages the check hashes are the goldens janua#814 and janua#820
    rendered from the code production runs, so equal hashes across the images
    mean English is byte for byte production's."""
    from app.routers.v1.auth import _switch_refused_html

    golden = ROOT / "apps/api/tests/unit/routers/fixtures/switch_refused_default"
    for key, name in (("switch_refused_cross_origin", "cross_origin"), ("switch_refused_not_held", "not_held")):
        assert _switch_refused_html(key).encode() == (golden / f"{name}.html").read_bytes(), name


def test_exception_record_names_the_owner_go_and_its_scope():
    approved = _record("Approved by")
    assert "2026-11-17" in approved
    assert "promote-to-prod.yml` stays held" in approved
    assert "this hotfix only (janua#814 and janua#820)" in approved
    assert WORKFLOW["env"]["BASE_IMAGE"].split("@", 1)[1] in _record("Replaces")


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard
