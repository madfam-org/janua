"""Staging source must never inherit production integrations or credentials."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
STAGING = ROOT / "k8s" / "overlays" / "staging"
API_SERVICE = "janua-api-staging"


def objects():
    kustomization = yaml.safe_load((STAGING / "kustomization.yaml").read_text())
    assert kustomization["namespace"] == "janua-staging"
    assert not set(kustomization) - {"apiVersion", "kind", "namespace", "resources", "images"}
    items = []
    for resource in kustomization["resources"]:
        assert Path(resource).name == resource  # Closed flat, product-owned inputs.
        items.extend(yaml.safe_load_all((STAGING / resource).read_text()))
    return items


def test_only_api_and_private_redis_workloads():
    workloads = [o for o in objects() if o["kind"] == "Deployment"]
    assert {o["metadata"]["name"] for o in workloads} == {API_SERVICE, "janua-staging-redis"}
    for workload in workloads:
        spec = workload["spec"]["template"]["spec"]
        assert spec["automountServiceAccountToken"] is False
        assert spec["securityContext"]["runAsNonRoot"] is True
        for container in spec["containers"]:
            assert container["securityContext"]["readOnlyRootFilesystem"] is True
            assert container["securityContext"]["allowPrivilegeEscalation"] is False


def test_runtime_has_only_fresh_staging_secret_references():
    api = next(
        o for o in objects() if o["kind"] == "Deployment" and o["metadata"]["name"] == API_SERVICE
    )
    environment = api["spec"]["template"]["spec"]["containers"][0]["env"]
    values = {e["name"]: e.get("value") for e in environment}
    assert values["EMAIL_ENABLED"] == "false"
    assert values["ENABLE_SIGNUPS"] == values["ENABLE_MAGIC_LINKS"] == "false"
    assert values["COOKIE_DOMAIN"] == ""
    assert values["DATABASE_SSL_MODE"] == "verify-full"
    assert values["DATABASE_SSL_CA_FILE"] == "/var/run/janua-staging/ca/ca.crt"
    assert (
        values["JWT_ISSUER"]
        == values["BASE_URL"]
        == values["FRONTEND_URL"]
        == "https://staging-auth.madfam.io"
    )
    assert values["CORS_ORIGINS"] == "https://staging-auth.madfam.io"
    for name in [
        "SMTP_HOST",
        "SMTP_PASSWORD",
        "RESEND_API_KEY",
        "CTM_RESEND_API_KEY",
        "CTM_TRACKING_HOST",
        "DHANAM_FEDERATION_URL",
        "FEDERATION_API_TOKEN",
        "JANUA_SERVICE_TOKEN",
        "INTERNAL_API_KEY",
    ]:
        assert values[name] == ""
    for entry in environment:
        if "valueFrom" in entry:
            assert entry["valueFrom"]["secretKeyRef"]["name"] == "janua-staging-secrets"
    assert "DIRECT_DATABASE_URL" not in values  # Migrator custody is a separate job.
    assert values["AUTO_MIGRATE"] == values["JANUA_APPLY_MIGRATIONS"] == "false"


def test_external_secret_paths_and_private_service_are_isolated():
    items = objects()
    for obj in items:
        assert obj["metadata"]["namespace"] == "janua-staging"
        assert obj["kind"] not in {"Secret", "Ingress", "NetworkPolicy", "Namespace"}
        if obj["kind"] == "ExternalSecret":
            for entry in obj["spec"]["data"]:
                assert entry["remoteRef"]["key"] == "secret/janua-staging"
        if obj["kind"] == "Service":
            assert obj["spec"]["type"] == "ClusterIP"


def test_staging_identity_matches_native_health_and_binding_without_production_alias():
    items = objects()
    deployment = next(
        o for o in items if o["kind"] == "Deployment" and o["metadata"]["name"] == API_SERVICE
    )
    service = next(
        o for o in items if o["kind"] == "Service" and o["metadata"]["name"] == API_SERVICE
    )
    selector = {"app": "janua-api", "enclii.dev/service": API_SERVICE}
    assert deployment["metadata"]["labels"]["enclii.dev/service"] == API_SERVICE
    assert service["metadata"]["labels"]["enclii.dev/service"] == API_SERVICE
    assert deployment["spec"]["selector"]["matchLabels"] == selector
    assert service["spec"]["selector"] == selector
    labels = deployment["spec"]["template"]["metadata"]["labels"]
    assert all(labels.get(key) == value for key, value in selector.items())
    assert labels["app.kubernetes.io/name"] == labels["app"] == "janua-api"
    assert deployment["spec"]["template"]["spec"]["containers"][0]["name"] == "janua-api"
    assert deployment["metadata"]["annotations"]["enclii.dev/reconcile"] == "disabled"
    assert not any(
        o["kind"] in {"Deployment", "Service"} and o["metadata"]["name"] == "janua-api"
        for o in items
    )
    legacy_labels = {"app": "janua-api", "enclii.dev/service": "janua-api"}
    assert not all(legacy_labels.get(key) == value for key, value in selector.items())
    production = yaml.safe_load((ROOT / "k8s/base/deployments/janua-api.yaml").read_text())
    assert production["metadata"]["name"] == "janua-api"
    assert production["spec"]["template"]["metadata"]["labels"]["app"] == "janua-api"
    assert (
        production["spec"]["template"]["metadata"]["labels"].get("enclii.dev/service")
        != API_SERVICE
    )


def test_promotion_rejects_unstaged_frontends():
    workflow = yaml.safe_load((ROOT / ".github/workflows/promote-to-prod.yml").read_text())
    trigger = workflow.get("on", workflow.get(True))  # PyYAML YAML1.1 recognizes on as bool.
    assert trigger["workflow_dispatch"]["inputs"]["component"]["options"] == ["api"]
    resolve = next(s for s in workflow["jobs"]["validate"]["steps"] if s.get("id") == "resolve")
    assert '[[ "$COMPONENT" != "api" ]]' in resolve["run"]


def test_staging_requires_dependencies_while_production_keeps_availability():
    api = next(
        o for o in objects() if o["kind"] == "Deployment" and o["metadata"]["name"] == API_SERVICE
    )
    container = api["spec"]["template"]["spec"]["containers"][0]
    assert container["readinessProbe"]["httpGet"]["path"] == (
        "/api/v1/health/ready?require_dependencies=true"
    )
    production = yaml.safe_load((ROOT / "k8s/base/deployments/janua-api.yaml").read_text())
    runtime = production["spec"]["template"]["spec"]["containers"][0]
    assert runtime["readinessProbe"]["httpGet"]["path"] == "/api/v1/health/ready"
