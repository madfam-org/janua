"""Staging source must never inherit production integrations or credentials."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[5]
STAGING = ROOT / "k8s" / "overlays" / "staging"


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
    assert {o["metadata"]["name"] for o in workloads} == {"janua-api", "janua-staging-redis"}
    for workload in workloads:
        spec = workload["spec"]["template"]["spec"]
        assert spec["automountServiceAccountToken"] is False
        assert spec["securityContext"]["runAsNonRoot"] is True
        for container in spec["containers"]:
            assert container["securityContext"]["readOnlyRootFilesystem"] is True
            assert container["securityContext"]["allowPrivilegeEscalation"] is False


def test_runtime_has_only_fresh_staging_secret_references():
    api = next(
        o for o in objects() if o["kind"] == "Deployment" and o["metadata"]["name"] == "janua-api"
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
    assert {o["kind"] for o in items} == {
        "Deployment", "Service", "PersistentVolumeClaim", "ExternalSecret", "NetworkPolicy", "Job",
    }
    for obj in items:
        assert obj["metadata"]["namespace"] == "janua-staging"
        if obj["kind"] == "ExternalSecret":
            for entry in obj["spec"]["data"]:
                assert entry["remoteRef"]["key"] == "secret/janua-staging"
        if obj["kind"] == "Service":
            assert obj["spec"]["type"] == "ClusterIP"
    assert {o["metadata"]["name"] for o in items if o["kind"] == "ExternalSecret"} == {
        "janua-staging-secrets", "janua-staging-ca", "janua-staging-redis",
        "janua-staging-acceptance",
    }


def pods(name):
    return {"matchLabels": {"app.kubernetes.io/name": name}}


def tcp(port):
    return [{"protocol": "TCP", "port": port}]


# The complete allowed set. Anything added, removed or widened fails here.
ALLOWED_NETWORK_POLICIES = {
    "janua-staging-redis-from-api": {
        "podSelector": pods("janua-staging-redis"),
        "policyTypes": ["Ingress", "Egress"],
        "ingress": [{"from": [{"podSelector": pods("janua-api")}], "ports": tcp(6379)}],
    },
    "janua-staging-api-to-redis": {
        "podSelector": pods("janua-api"),
        "policyTypes": ["Egress"],
        "egress": [{"to": [{"podSelector": pods("janua-staging-redis")}], "ports": tcp(6379)}],
    },
    "janua-staging-api-to-cnpg": {
        "podSelector": pods("janua-api"),
        "policyTypes": ["Egress"],
        "egress": [{"to": [{
            "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "project-569a23e7"}},
            "podSelector": {"matchLabels": {"cnpg.io/podRole": "instance"}},
        }], "ports": tcp(5432)}],
    },
    "janua-staging-admission-to-api": {
        "podSelector": pods("janua-staging-admission"),
        "policyTypes": ["Ingress", "Egress"],
        "egress": [{"to": [{"podSelector": pods("janua-api")}], "ports": tcp(8080)}],
    },
    "janua-staging-dns": {
        "podSelector": {"matchExpressions": [{
            "key": "app.kubernetes.io/name", "operator": "In",
            "values": ["janua-api", "janua-staging-admission"],
        }]},
        "policyTypes": ["Egress"],
        "egress": [{"to": [{"namespaceSelector": {
            "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}}],
            "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}]}],
    },
}


def test_network_policies_are_exactly_the_allowed_set():
    policies = {o["metadata"]["name"]: o["spec"] for o in objects() if o["kind"] == "NetworkPolicy"}
    assert policies == ALLOWED_NETWORK_POLICIES
    # The API's ingress stays unselected: the public host and probes are untouched.
    api = [n for n, p in policies.items() if p["podSelector"] == pods("janua-api")]
    assert all(policies[n]["policyTypes"] == ["Egress"] for n in api)


def test_policies_select_the_labels_the_workloads_carry():
    templates = {o["metadata"]["name"]: o["spec"]["template"]["metadata"]["labels"]
                 for o in objects() if o["kind"] in {"Deployment", "Job"}}
    assert templates["janua-api"]["app.kubernetes.io/name"] == "janua-api"
    assert templates["janua-staging-redis"]["app.kubernetes.io/name"] == "janua-staging-redis"
    assert templates["janua-staging-admission"]["app.kubernetes.io/name"] == "janua-staging-admission"
    api_ports = [p["containerPort"] for c in next(
        o for o in objects() if o["metadata"]["name"] == "janua-api" and o["kind"] == "Deployment"
    )["spec"]["template"]["spec"]["containers"] for p in c["ports"]]
    assert 8080 in api_ports


def test_admission_job_is_a_postsync_probe_without_database_credentials():
    jobs = [o for o in objects() if o["kind"] == "Job"]
    assert [j["metadata"]["name"] for j in jobs] == ["janua-staging-admission"]
    job = jobs[0]
    assert job["metadata"]["annotations"] == {
        "argocd.argoproj.io/hook": "PostSync",
        "argocd.argoproj.io/hook-delete-policy": "BeforeHookCreation",
    }
    assert job["spec"]["backoffLimit"] == 0  # Non-idempotent steps are never retried.
    spec = job["spec"]["template"]["spec"]
    assert spec["restartPolicy"] == "Never"
    assert spec["automountServiceAccountToken"] is False
    assert spec["securityContext"]["runAsNonRoot"] is True
    [container] = spec["containers"]
    assert container["image"] == "ghcr.io/madfam-org/janua-api"  # Pinned by the images: digest.
    assert container["command"] == [
        "python", "-m", "app.staging_admission",
        "--base-url", "http://janua-api.janua-staging.svc.cluster.local",
    ]
    security = container["securityContext"]
    assert security["readOnlyRootFilesystem"] is True
    assert security["allowPrivilegeEscalation"] is False
    assert security["capabilities"]["drop"] == ["ALL"]
    assert container["resources"]["limits"] == {"cpu": "500m", "memory": "320Mi"}
    env = {e["name"]: e["valueFrom"]["secretKeyRef"] for e in container["env"]}
    assert env == {
        "STAGING_OPERATOR_PASSWORD": {"name": "janua-staging-acceptance", "key": "operator-password"},
        "STAGING_INVITEE_PASSWORD": {"name": "janua-staging-acceptance", "key": "invitee-password"},
        "STAGING_FOREIGN_PASSWORD": {"name": "janua-staging-acceptance", "key": "foreign-password"},
    }
    assert "envFrom" not in container


def test_acceptance_secret_carries_only_the_three_synthetic_passwords():
    secret = next(o for o in objects()
                  if o["kind"] == "ExternalSecret" and o["metadata"]["name"] == "janua-staging-acceptance")
    assert secret["spec"]["target"]["name"] == "janua-staging-acceptance"
    assert {(d["secretKey"], d["remoteRef"]["property"]) for d in secret["spec"]["data"]} == {
        ("operator-password", "operator_password"),
        ("invitee-password", "invitee_password"),
        ("foreign-password", "foreign_password"),
    }


def test_promotion_rejects_unstaged_frontends():
    workflow = yaml.safe_load((ROOT / ".github/workflows/promote-to-prod.yml").read_text())
    trigger = workflow.get("on", workflow.get(True))  # PyYAML YAML1.1 recognizes on as bool.
    assert trigger["workflow_dispatch"]["inputs"]["component"]["options"] == ["api"]
    resolve = next(s for s in workflow["jobs"]["validate"]["steps"] if s.get("id") == "resolve")
    assert '[[ "$COMPONENT" != "api" ]]' in resolve["run"]
