"""Offline source probes: no real staging/prod calls, identities or credentials."""

import base64
import copy
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[5]
SPEC = importlib.util.spec_from_file_location(
    "janua_public_probe", ROOT / "scripts/staging/public_probe.py"
)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


def key(modulus_offset, kid):
    # Synthetic metadata; cryptographic signing is not this public-read probe.
    modulus = (1 << 2047) + modulus_offset
    return {
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "kid": kid,
        "e": "AQAB",
        "n": base64.urlsafe_b64encode(modulus.to_bytes(256, "big")).decode().rstrip("="),
    }


@pytest.fixture
def responses():
    stage = PROBE.STAGE
    return {
        stage + "/health": {"status": "healthy", "environment": "staging"},
        stage + "/api/v1/health/ready?require_dependencies=true": {
            "status": "ready",
            "degraded": [],
            "redis": "healthy",
            "database": {"healthy": True, "status": "healthy"},
        },
        stage + "/.well-known/openid-configuration": {
            "issuer": stage,
            "authorization_endpoint": stage + "/api/v1/oauth/authorize",
            "token_endpoint": stage + "/api/v1/oauth/token",
            "userinfo_endpoint": stage + "/api/v1/oauth/userinfo",
            "jwks_uri": stage + "/.well-known/jwks.json",
            "introspection_endpoint": stage + "/api/v1/oauth/introspect",
            "revocation_endpoint": stage + "/api/v1/oauth/revoke",
            "end_session_endpoint": stage + "/logout",
            "registration_endpoint": stage + "/api/v1/oauth/register",
        },
        stage + "/.well-known/jwks.json": {"keys": [key(13, "synthetic-stage")]},
        PROBE.PROD + "/.well-known/jwks.json": {"keys": [key(17, "synthetic-production")]},
    }


def test_valid_metadata_is_explicitly_insufficient_to_authorize_promotion(responses):
    requested = []

    def fetch(url):
        requested.append(url)
        return responses[url]

    result = PROBE.probe(fetch)
    assert result["public_metadata_ready"] is True
    assert result["classification"] == "PUBLIC_SURFACE_ONLY"
    assert not any(
        result[name]
        for name in (
            "runtime_image_proven",
            "native_isolation_proven",
            "runtime_soak_proven",
            "promotion_authorized",
        )
    )
    assert set(requested) == set(responses)


@pytest.mark.parametrize(
    "condition",
    [
        "wrong-environment",
        "degraded",
        "missing-db",
        "bad-redis",
        "prod-issuer",
        "prod-endpoint",
        "same-key",
        "same-modulus-other-exponent",
        "private-key",
        "weak-key",
        "empty-keys",
        "duplicate-kid",
    ],
)
def test_unhealthy_or_nonisolated_metadata_refuses(responses, condition):
    stage = PROBE.STAGE
    ready = responses[stage + "/api/v1/health/ready?require_dependencies=true"]
    metadata = responses[stage + "/.well-known/openid-configuration"]
    keys = responses[stage + "/.well-known/jwks.json"]["keys"]
    if condition == "wrong-environment":
        responses[stage + "/health"]["environment"] = "production"
    elif condition == "degraded":
        ready["degraded"] = ["database"]
    elif condition == "missing-db":
        ready.pop("database")
    elif condition == "bad-redis":
        ready["redis"] = "unhealthy"
    elif condition == "prod-issuer":
        metadata["issuer"] = PROBE.PROD
    elif condition == "prod-endpoint":
        metadata["token_endpoint"] = PROBE.PROD + "/api/v1/oauth/token"
    elif condition in {"same-key", "same-modulus-other-exponent"}:
        keys[:] = copy.deepcopy(responses[PROBE.PROD + "/.well-known/jwks.json"]["keys"])
        if condition == "same-modulus-other-exponent":
            keys[0]["e"] = "Aw"
    elif condition == "private-key":
        keys[0]["d"] = "synthetic-invalid-private-material"
    elif condition == "weak-key":
        keys[0]["n"] = "AQAB"
    elif condition == "empty-keys":
        keys.clear()
    elif condition == "duplicate-kid":
        keys.append(copy.deepcopy(keys[0]))
    with pytest.raises(PROBE.ProbeRefused):
        PROBE.probe(responses.__getitem__)


def test_duplicate_json_keys_refuse():
    with pytest.raises(PROBE.ProbeRefused):
        json.loads('{"issuer":"one","issuer":"two"}', object_pairs_hook=PROBE._unique_object)


def test_promotion_hold_has_no_environment_or_argument_bypass():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/staging/promotion_runtime_guard.py"), "--approved"],
        env={
            **os.environ,
            "JANUA_STAGING_QUALIFIED": "true",
            "INPUT_BREAK_GLASS_WITHOUT_SOAK": "true",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "JANUA_STAGING_RUNTIME_NOT_QUALIFIED" in result.stderr
    workflow = yaml.safe_load((ROOT / ".github/workflows/promote-to-prod.yml").read_text())
    assert "staging-runtime-guard" in workflow["jobs"]["validate"]["needs"]


@pytest.mark.parametrize(
    "body,status",
    [
        (b'{"value":1,"value":2}', 200),
        (b"[]", 200),
        (b"x" * (PROBE.MAX_BYTES + 1), 200),
        (b"{}", 302),
    ],
)
def test_http_metadata_reader_refuses_ambiguous_or_unbounded_responses(monkeypatch, body, status):
    from contextlib import nullcontext
    from types import SimpleNamespace

    calls = []

    def open_response(request, timeout):
        calls.append((request.full_url, timeout))
        return nullcontext(SimpleNamespace(status=status, read=lambda size: body[:size]))

    monkeypatch.setattr(
        PROBE.urllib.request, "build_opener", lambda *a: SimpleNamespace(open=open_response)
    )
    with pytest.raises(PROBE.ProbeRefused):
        PROBE.fetch_json(PROBE.STAGE + "/.well-known/jwks.json")
    assert calls == [(PROBE.STAGE + "/.well-known/jwks.json", 10)]


def test_failed_probe_never_prints_upstream_details(monkeypatch, capsys):
    def failure():
        raise OSError("synthetic-private-upstream-detail")

    monkeypatch.setattr(PROBE, "probe", failure)
    assert PROBE.main() == 1
    output = capsys.readouterr()
    assert "synthetic-private-upstream-detail" not in output.out + output.err
    assert json.loads(output.out) == {
        "classification": "PUBLIC_SURFACE_REFUSED",
        "promotion_authorized": False,
    }
