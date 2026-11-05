"""The production Kyverno signature exception may only shrink.

k8s/overlays/production/kyverno-policy-exception.yaml exempts Janua workloads
from the cluster's verify-image-signatures policy. It is being removed one
workload at a time (docs/runbooks/production-gitops-reconcile.md, section 2).
These checks stop it from silently regrowing or widening.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
OVERLAY = ROOT / "k8s/overlays/production"
EXCEPTION = OVERLAY / "kyverno-policy-exception.yaml"

# Workloads still exempt. Remove names as stages land; never add one back.
STILL_EXEMPT = {"janua-api*", "janua-admin*", "janua-dashboard*"}
VERIFIED = {"janua-website*", "janua-docs*"}


def exception():
    return yaml.safe_load(EXCEPTION.read_text())


def matched_names():
    names = set()
    for entry in exception()["spec"]["match"]["any"]:
        names.update(entry["resources"].get("names", []))
    return names


def test_exception_only_shrinks():
    names = matched_names()
    assert names <= STILL_EXEMPT, names - STILL_EXEMPT
    assert not names & VERIFIED


def test_exception_stays_scoped_to_janua_and_the_signature_policy():
    doc = exception()
    assert doc["metadata"]["namespace"] == "janua"
    assert [e["policyName"] for e in doc["spec"]["exceptions"]] == ["verify-image-signatures"]
    for entry in doc["spec"]["match"]["any"]:
        resources = entry["resources"]
        assert resources.get("namespaces") == ["janua"]
        # Every match is by name: no selector or wildcard that could cover new workloads.
        assert resources.get("names"), resources
        assert set(resources) <= {"kinds", "namespaces", "names"}, resources
        assert all(n.startswith("janua-") and n != "janua-*" for n in resources["names"])


def test_overlay_still_lists_the_exception_while_any_name_remains():
    resources = yaml.safe_load((OVERLAY / "kustomization.yaml").read_text())["resources"]
    if matched_names():
        assert "kyverno-policy-exception.yaml" in resources
