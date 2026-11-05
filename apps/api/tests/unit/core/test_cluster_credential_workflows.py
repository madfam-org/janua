"""Workflows that hold the production kubeconfig cannot change what production runs.

Images reach production only through the production overlay, written by
promote-to-prod.yml (with its guards and the isolated-staging hold) or
rollback-prod.yml. A workflow with direct cluster credentials must therefore
either only read, or apply exactly main's production overlay -- and its
free-text inputs must never become shell code.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[5]
WORKFLOWS = ROOT / ".github/workflows"
KUBECONFIG = "secrets.KUBECONFIG_PRODUCTION"
ENVIRONMENT = "production-cluster"

# Every workflow allowed to hold the production kubeconfig. Adding one is a
# reviewed decision: it must appear here, with what it may do.
ALLOWED = {
    "sync-prod-gitops.yml": "apply-main-overlay",
    "drift-check.yml": "read-only",
    "diagnose-cluster.yml": "read-only",
}
# Verbs that change the cluster, or run code in it (exec, cp, debug, run, attach).
MUTATING = re.compile(
    r"\bkubectl\s+(apply|create|delete|patch|scale|set|annotate|label|replace|edit"
    r"|cordon|drain|taint|exec|cp|debug|run|attach|rollout\s+(restart|undo|pause|resume))\b"
)
INLINED_INPUT = re.compile(r"\$\{\{\s*(inputs|github\.event\.inputs)\.")
DEPLOYMENTS = ["janua-api", "janua-admin", "janua-dashboard", "janua-docs", "janua-website"]


def load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


def steps(workflow):
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


def scripts(workflow):
    return [step["run"] for step in steps(workflow) if "run" in step]


def test_only_reviewed_workflows_hold_the_production_kubeconfig():
    holders = {p.name for p in WORKFLOWS.glob("*.y*ml") if KUBECONFIG in p.read_text()}
    assert holders == set(ALLOWED)


@pytest.mark.parametrize("name", sorted(ALLOWED))
def test_every_job_reading_the_kubeconfig_uses_the_main_only_environment(name):
    # The secret belongs in an environment that only main may deploy to. A job
    # outside it would read a repository-level copy, available to any branch.
    jobs = {
        job_id: job
        for job_id, job in load(name)["jobs"].items()
        if KUBECONFIG in yaml.safe_dump(job, width=10_000)
    }
    assert jobs, f"{name} no longer reads {KUBECONFIG}; update ALLOWED"
    for job_id, job in jobs.items():
        assert job.get("environment") == ENVIRONMENT, f"{name}:{job_id}"


@pytest.mark.parametrize("name", sorted(n for n, role in ALLOWED.items() if role == "read-only"))
def test_read_only_workflows_never_change_the_cluster(name):
    for script in scripts(load(name)):
        assert not MUTATING.search(script), script


@pytest.mark.parametrize("name", sorted(ALLOWED))
def test_free_text_inputs_never_become_shell_code(name):
    for script in scripts(load(name)):
        assert not INLINED_INPUT.search(script), script


def test_sync_prod_changes_only_argo_state_the_pull_secret_and_main_overlay():
    workflow = load("sync-prod-gitops.yml")
    mutations = sorted(
        line[m.start() :].strip()
        for script in scripts(workflow)
        for line in script.splitlines()
        if (m := MUTATING.search(line))
    )
    # Refresh the janua pull secret, clear/refresh the Argo operation, apply
    # the rendered production overlay. Anything new here needs review.
    expected = [
        "kubectl annotate application",
        "kubectl apply -f -",
        "kubectl apply -f /tmp/janua-production.yaml",
        "kubectl patch application",
    ]
    assert len(mutations) == len(expected), mutations
    for line, prefix in zip(mutations, expected):
        assert line.startswith(prefix), (line, prefix)
    applied = [s for s in scripts(workflow) if "kubectl apply -f /tmp/janua-production.yaml" in s]
    assert len(applied) == 1
    assert "kustomize build k8s/overlays/production > /tmp/janua-production.yaml" in applied[0]


def sync_guard():
    workflow = load("sync-prod-gitops.yml")
    return workflow, steps(workflow)[0]


def test_sync_prod_guard_runs_before_anything_else():
    workflow, guard = sync_guard()
    assert "run" in guard and "refs/heads/main" in guard["run"]
    checkout = next(s for s in steps(workflow) if s.get("uses", "").startswith("actions/checkout@"))
    # main's tip, never the dispatch ref's snapshot.
    assert checkout["with"]["ref"] == "refs/heads/main"


def run_sync_guard(ref, component):
    _, guard = sync_guard()
    env = {**os.environ, "REF": ref, "COMPONENT": component}
    return subprocess.run(["bash", "-c", guard["run"]], env=env, capture_output=True, text=True)


@pytest.mark.parametrize("component", ["", *DEPLOYMENTS])
def test_sync_prod_guard_accepts_main_and_known_deployments(component):
    result = run_sync_guard("refs/heads/main", component)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("ref", ["refs/heads/feature", "refs/heads/main-copy", "refs/tags/v1.0.0"])
def test_sync_prod_guard_refuses_other_refs(ref):
    result = run_sync_guard(ref, "janua-website")
    assert result.returncode != 0
    assert "runs only from main" in result.stderr


@pytest.mark.parametrize(
    "component", ["janua-api; true", "$(true)", "janua-worker", "kube-system/x", " janua-api"]
)
def test_sync_prod_guard_refuses_unknown_components(component):
    result = run_sync_guard("refs/heads/main", component)
    assert result.returncode != 0
    assert "component must be one of" in result.stderr


def run_diagnose_validation(namespace, deployment):
    workflow = load("diagnose-cluster.yml")
    first = steps(workflow)[0]
    assert first["name"] == "Validate inputs"
    env = {**os.environ, "NS": namespace, "DEPLOYMENT": deployment}
    return subprocess.run(["bash", "-c", first["run"]], env=env, capture_output=True, text=True)


@pytest.mark.parametrize(("namespace", "deployment"), [("janua", ""), ("janua", "janua-api")])
def test_diagnose_accepts_kubernetes_names(namespace, deployment):
    result = run_diagnose_validation(namespace, deployment)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("namespace", "deployment"),
    [("", ""), ("janua; true", ""), ("janua", "x$(true)"), ("Janua", ""), ("janua", "-n")],
)
def test_diagnose_refuses_anything_else(namespace, deployment):
    result = run_diagnose_validation(namespace, deployment)
    assert result.returncode != 0
