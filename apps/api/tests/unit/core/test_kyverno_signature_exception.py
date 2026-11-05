"""Janua production workloads stay under Kyverno image-signature verification.

The PolicyException that exempted Janua workloads from verify-image-signatures
(k8s/overlays/production/kyverno-policy-exception.yaml) was removed in stages on
2026-11-05. These checks stop it, or an equivalent, from coming back.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
OVERLAY = ROOT / "k8s/overlays/production"


def test_signature_exception_is_removed():
    assert not (OVERLAY / "kyverno-policy-exception.yaml").exists()
    resources = yaml.safe_load((OVERLAY / "kustomization.yaml").read_text())["resources"]
    assert "kyverno-policy-exception.yaml" not in resources


def test_no_manifest_exempts_janua_from_signature_verification():
    for path in sorted((ROOT / "k8s").rglob("*.y*ml")):
        for doc in yaml.safe_load_all(path.read_text()):
            if not isinstance(doc, dict) or doc.get("kind") != "PolicyException":
                continue
            policies = [e.get("policyName") for e in doc.get("spec", {}).get("exceptions", [])]
            assert "verify-image-signatures" not in policies, path
