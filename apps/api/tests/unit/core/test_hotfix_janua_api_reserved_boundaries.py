"""The reserved-boundaries hotfix stays exactly as narrow as it was reviewed.

deployment/hotfix/janua-api-reserved-boundaries builds the image production
runs plus two reviewed files (the OAuth reservation registry and the discovery
fix), because the promotion hold (scripts/staging/promotion_runtime_guard.py)
blocks normal promotions. These tests keep the Dockerfile and its workflow from
quietly widening, and pin the registry comparison that refuses any image whose
registry is not strictly tighter than production's.
"""

from __future__ import annotations

import importlib.util
import re
import types
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
HOTFIX = ROOT / "deployment/hotfix/janua-api-reserved-boundaries"
DOCKERFILE = HOTFIX / "Dockerfile"
WORKFLOW_PATH = ROOT / ".github/workflows/hotfix-janua-api-reserved-boundaries.yml"
WORKFLOW = yaml.safe_load(WORKFLOW_PATH.read_text())
COPIED = (
    "apps/api/app/core/oauth_metadata.py",
    "apps/api/app/core/reserved_oauth_boundaries.py",
)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HOTFIX / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare_registry = _load("compare_registry")
dump_registry = _load("dump_registry")


def _instructions() -> list[str]:
    lines = DOCKERFILE.read_text().splitlines()
    return [line for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _steps() -> list[dict]:
    return WORKFLOW["jobs"]["build"]["steps"]


def _run_scripts() -> str:
    return "\n".join(step.get("run", "") for step in _steps())


# --- Dockerfile and workflow shape -------------------------------------------


def test_dockerfile_is_one_pinned_base_and_one_copy_of_two_files():
    instructions = _instructions()
    assert len(instructions) == 2, instructions
    base, copy = instructions
    assert re.fullmatch(r"FROM ghcr\.io/madfam-org/janua-api@sha256:[0-9a-f]{64}", base), base
    assert copy == f"COPY --chown=janua:python {' '.join(COPIED)} /app/app/core/"


def test_workflow_verifies_the_base_the_dockerfile_pins():
    base = _instructions()[0].removeprefix("FROM ")
    env = WORKFLOW["env"]
    assert env["BASE_IMAGE"] == base
    assert env["DOCKERFILE"] == str(DOCKERFILE.relative_to(ROOT))
    assert env["HOTFIX_DIR"] == str(HOTFIX.relative_to(ROOT))
    assert re.fullmatch(r"[0-9a-f]{40}", env["BASE_SOURCE"])


def test_base_is_the_same_production_image_the_762_hotfix_verified():
    """Both exceptions start from one verified production image and source."""
    other = yaml.safe_load((ROOT / ".github/workflows/hotfix-janua-api-762.yml").read_text())
    assert WORKFLOW["env"]["BASE_IMAGE"] == other["env"]["BASE_IMAGE"]
    assert WORKFLOW["env"]["BASE_SOURCE"] == other["env"]["BASE_SOURCE"]


def test_workflow_is_manual_and_from_main_only():
    # PyYAML reads the bare key `on` as True.
    triggers = WORKFLOW.get("on", WORKFLOW.get(True))
    assert set(triggers) == {"workflow_dispatch"}
    first = _steps()[0]
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


def test_workflow_expects_exactly_the_copied_files_and_compares_each():
    step = next(s for s in _steps() if s.get("name") == "Hotfix differs from the base by two files")
    for path in COPIED:
        name = Path(path).name
        assert (
            f"/tmp/hotfix/base/app/core/{name} and /tmp/hotfix/new/app/core/{name} differ"
            in step["run"]
        )
        assert f"cmp /tmp/hotfix/new/app/core/{name} {path}" in step["run"]
    assert "base_layers + 1" in step["run"]


def test_checks_use_a_driver_the_production_image_has():
    step = next(
        s
        for s in _steps()
        if s.get("name") == "Discovery loses registration_endpoint; registry only tightens"
    )
    urls = re.findall(r"DATABASE_URL='([^']*)'", step["run"])
    assert urls and all(url.startswith("postgresql+asyncpg://") for url in urls), urls
    assert '"$HOTFIX_DIR/dump_registry.py"' in step["run"]
    assert '"$HOTFIX_DIR/compare_registry.py"' in step["run"]
    requirements = (ROOT / "apps/api/requirements.txt").read_text()
    assert re.search(r"^asyncpg\b", requirements, re.M)


def test_workflow_checks_source_delta_and_behaviour_before_signing():
    names = [step.get("name", "") for step in _steps()]
    order = [
        "Base image is BASE_SOURCE",
        "Build and push",
        "Hotfix differs from the base by two files",
        "Discovery loses registration_endpoint; registry only tightens",
        "Sign image with cosign",
    ]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions), names


def test_promotion_hold_is_untouched():
    guard = (ROOT / "scripts/staging/promotion_runtime_guard.py").read_text()
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in guard
    assert "return 1" in guard


# --- Registry comparison ------------------------------------------------------


def _registry(**overrides) -> dict:
    values = {
        "RESERVED_SCOPES": {"kind": "set", "items": ["admin", "billing:events"]},
        "RESERVED_AUDIENCES": {"kind": "set", "items": ["dhanam-api", "janua-email"]},
        "RESERVED_CLIENT_NAMES": {"kind": "set", "items": ["selva-office-gmail"]},
        "DHANAM_SCOPES": {"kind": "set", "items": ["billing:events"]},
        "RESERVED_AUDIENCE_PREFIXES": {"kind": "seq", "items": ["janua-"]},
        "FIRST_PARTY_NAME_PREFIXES": {"kind": "seq", "items": ["selva-office", "madfam-"]},
        "SILENT_AUTH_SCOPE": {"kind": "str", "value": "madfam:silent_auth"},
        "TENANT_BOUND_MACHINE_SCOPES": {"kind": "keys", "items": ["hcm:hr"]},
    }
    values.update(overrides.pop("values", {}))
    registry = {
        "names": sorted(values) + ["is_reserved_scope"],
        "values": values,
        "self_consistent": True,
    }
    registry.update(overrides)
    return registry


def test_compare_accepts_added_reservations_and_reports_them():
    base = _registry()
    new = _registry(
        values={
            "RESERVED_SCOPES": {
                "kind": "set",
                "items": ["admin", "billing:events", "dhanam-cost-events:write"],
            },
            "RESERVED_AUDIENCES": {
                "kind": "set",
                "items": ["dhanam-api", "janua-email", "phynd-crm"],
            },
            "PHYND_CRM_SCOPES": {"kind": "set", "items": ["phynd-crm-engagements:read"]},
        }
    )
    errors, added = compare_registry.compare(base, new)
    assert errors == []
    assert added["RESERVED_SCOPES"] == ["dhanam-cost-events:write"]
    assert added["RESERVED_AUDIENCES"] == ["phynd-crm"]
    assert "PHYND_CRM_SCOPES" not in added  # new names have no base to compare against


def test_compare_accepts_an_identical_registry():
    assert compare_registry.compare(_registry(), _registry()) == ([], {})


def test_compare_refuses_a_lost_reservation():
    new = _registry(values={"RESERVED_SCOPES": {"kind": "set", "items": ["admin"]}})
    errors, _ = compare_registry.compare(_registry(), new)
    assert any("RESERVED_SCOPES lost values" in e and "billing:events" in e for e in errors)


def test_compare_refuses_a_lost_component_set_value():
    new = _registry(values={"DHANAM_SCOPES": {"kind": "set", "items": []}})
    errors, _ = compare_registry.compare(_registry(), new)
    assert any(e.startswith("DHANAM_SCOPES lost values") for e in errors)


def test_compare_refuses_a_widened_first_party_prefix():
    new = _registry(
        values={
            "FIRST_PARTY_NAME_PREFIXES": {"kind": "seq", "items": ["selva-office", "madfam-", "x-"]}
        }
    )
    errors, _ = compare_registry.compare(_registry(), new)
    assert any(e.startswith("FIRST_PARTY_NAME_PREFIXES changed") for e in errors)


def test_compare_refuses_a_changed_constant_and_tenant_bound_list():
    new = _registry(
        values={
            "SILENT_AUTH_SCOPE": {"kind": "str", "value": "other"},
            "TENANT_BOUND_MACHINE_SCOPES": {"kind": "keys", "items": ["hcm:hr", "x:read"]},
        }
    )
    errors, _ = compare_registry.compare(_registry(), new)
    assert any(e.startswith("SILENT_AUTH_SCOPE changed") for e in errors)
    assert any(e.startswith("TENANT_BOUND_MACHINE_SCOPES changed") for e in errors)


def test_compare_refuses_a_removed_name_and_a_changed_kind():
    base = _registry()
    new = _registry(values={"DHANAM_SCOPES": {"kind": "seq", "items": ["billing:events"]}})
    new["names"] = [n for n in new["names"] if n != "is_reserved_scope"]
    errors, _ = compare_registry.compare(base, new)
    assert any("public names removed" in e and "is_reserved_scope" in e for e in errors)
    assert any(e.startswith("DHANAM_SCOPES changed kind") for e in errors)


def test_compare_refuses_a_missing_required_set_and_inconsistent_predicates():
    new = _registry(self_consistent=False)
    del new["values"]["RESERVED_CLIENT_NAMES"]
    errors, _ = compare_registry.compare(_registry(), new)
    assert any("RESERVED_CLIENT_NAMES is missing" in e for e in errors)
    assert any("disagree" in e for e in errors)


def test_compare_main_exit_codes(tmp_path, capsys):
    import json

    base = tmp_path / "base.json"
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    base.write_text(json.dumps(_registry()))
    good.write_text(json.dumps(_registry()))
    bad.write_text(json.dumps(_registry(values={"RESERVED_SCOPES": {"kind": "set", "items": []}})))
    assert compare_registry.main(["x", str(base), str(good)]) == 0
    assert "strictly tighter" in capsys.readouterr().out
    assert compare_registry.main(["x", str(base), str(bad)]) == 1
    assert "::error::RESERVED_SCOPES lost values" in capsys.readouterr().out
    assert compare_registry.main(["x"]) == 2


# --- Registry snapshot --------------------------------------------------------


def test_snapshot_encodes_authority_values_and_skips_the_rest():
    fake = types.ModuleType("fake_registry")
    fake.RESERVED_SCOPES = frozenset({"b", "a"})
    fake.RESERVED_AUDIENCES = frozenset({"janua-email"})
    fake.PREFIXES = ("janua-",)
    fake.SCOPE = "admin"
    fake.TENANT = {"hcm:hr": "why"}
    fake.is_reserved_scope = lambda s: s in fake.RESERVED_SCOPES
    fake.is_reserved_audience = lambda a: a in fake.RESERVED_AUDIENCES
    fake._private = "skip"
    snap = dump_registry.snapshot(fake)
    assert snap["values"]["RESERVED_SCOPES"] == {"kind": "set", "items": ["a", "b"]}
    assert snap["values"]["PREFIXES"] == {"kind": "seq", "items": ["janua-"]}
    assert snap["values"]["SCOPE"] == {"kind": "str", "value": "admin"}
    assert snap["values"]["TENANT"] == {"kind": "keys", "items": ["hcm:hr"]}
    assert "is_reserved_scope" in snap["names"] and "is_reserved_scope" not in snap["values"]
    assert "_private" not in snap["names"]
    assert snap["self_consistent"] is True


def test_snapshot_flags_predicates_that_disagree_with_the_sets():
    fake = types.ModuleType("fake_registry")
    fake.RESERVED_SCOPES = frozenset({"a"})
    fake.RESERVED_AUDIENCES = frozenset()
    fake.is_reserved_scope = lambda s: False
    fake.is_reserved_audience = lambda a: True
    assert dump_registry.snapshot(fake)["self_consistent"] is False


def test_snapshot_of_the_real_registry_is_self_consistent_and_tighter_than_itself():
    from app.core import reserved_oauth_boundaries

    snap = dump_registry.snapshot(reserved_oauth_boundaries)
    assert snap["self_consistent"] is True
    for name in ("RESERVED_SCOPES", "RESERVED_AUDIENCES", "RESERVED_CLIENT_NAMES"):
        assert snap["values"][name]["kind"] == "set"
    assert compare_registry.compare(snap, snap) == ([], {})
