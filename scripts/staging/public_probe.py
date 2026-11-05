"""Read-only public staging probe, never a native qualification or promotion token.

No login, user lookup, token mint, email, secret or workload operation. All URLs
are fixed public metadata endpoints; redirects, duplicate JSON keys and oversized
bodies refuse. Never print upstream payloads, keys or exceptions.
"""

import base64
import hashlib
import json
import urllib.request

STAGE = "https://staging-auth.madfam.io"
PROD = "https://auth.madfam.io"
MAX_BYTES = 1024 * 1024


class ProbeRefused(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProbeRefused("duplicate_json_key")
        result[key] = value
    return result


def fetch_json(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "Janua-Staging-Probe/1.0"}
    )
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=10) as response:
        if response.status != 200:
            raise ProbeRefused("http_status")
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ProbeRefused("response_too_large")
    value = json.loads(body, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ProbeRefused("invalid_metadata")
    return value


def _key_set(document):
    keys = document.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ProbeRefused("missing_public_keys")
    fingerprints, kids = set(), set()
    for key in keys:
        if (
            not isinstance(key, dict)
            or key.get("kty") != "RSA"
            or key.get("alg") != "RS256"
            or key.get("use") != "sig"
            or not isinstance(key.get("kid"), str)
            or not key["kid"]
            or key["kid"] in kids
            or {"d", "p", "q", "dp", "dq", "qi", "k"} & key.keys()
        ):
            raise ProbeRefused("invalid_public_keys")
        public = {name: key.get(name) for name in ("e", "kty", "n")}
        for name in ("e", "n"):
            value = public[name]
            if (
                not isinstance(value, str)
                or not value
                or any(
                    c
                    not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
                    for c in value
                )
            ):
                raise ProbeRefused("invalid_rsa_encoding")
        modulus = int.from_bytes(
            base64.urlsafe_b64decode(public["n"] + "=" * (-len(public["n"]) % 4)), "big"
        )
        if modulus.bit_length() < 2048:
            raise ProbeRefused("weak_public_key")
        exponent = int.from_bytes(
            base64.urlsafe_b64decode(public["e"] + "=" * (-len(public["e"]) % 4)), "big"
        )
        if exponent < 3 or exponent % 2 == 0:
            raise ProbeRefused("invalid_rsa_exponent")
        # Equal moduli share prime factors/private custody even if the exponent
        # or a noncanonical base64 representation differs. Compare the integer.
        fingerprint = hashlib.sha256(
            modulus.to_bytes((modulus.bit_length() + 7) // 8, "big")
        ).digest()
        if fingerprint in fingerprints:
            raise ProbeRefused("duplicate_public_key")
        fingerprints.add(fingerprint)
        kids.add(key["kid"])
    return fingerprints


def probe(fetch=fetch_json):
    health = fetch(STAGE + "/health")
    if health.get("status") != "healthy" or health.get("environment") != "staging":
        raise ProbeRefused("staging_health")
    ready = fetch(STAGE + "/api/v1/health/ready?require_dependencies=true")
    if (
        ready.get("status") != "ready"
        or ready.get("degraded") != []
        or ready.get("redis") != "healthy"
        or ready.get("database") != {"healthy": True, "status": "healthy"}
    ):
        raise ProbeRefused("staging_dependencies")
    discovery = fetch(STAGE + "/.well-known/openid-configuration")
    expected = {
        "issuer": STAGE,
        "authorization_endpoint": STAGE + "/api/v1/oauth/authorize",
        "token_endpoint": STAGE + "/api/v1/oauth/token",
        "userinfo_endpoint": STAGE + "/api/v1/oauth/userinfo",
        "jwks_uri": STAGE + "/.well-known/jwks.json",
        "introspection_endpoint": STAGE + "/api/v1/oauth/introspect",
        "revocation_endpoint": STAGE + "/api/v1/oauth/revoke",
        "end_session_endpoint": STAGE + "/logout",
    }
    if any(discovery.get(name) != value for name, value in expected.items()):
        raise ProbeRefused("staging_issuer")
    stage_keys = _key_set(fetch(STAGE + "/.well-known/jwks.json"))
    prod_keys = _key_set(fetch(PROD + "/.well-known/jwks.json"))
    if stage_keys & prod_keys:
        raise ProbeRefused("production_key_reuse")
    return {
        "classification": "PUBLIC_SURFACE_ONLY",
        "public_metadata_ready": True,
        "production_key_overlap": False,
        "runtime_image_proven": False,
        "native_isolation_proven": False,
        "runtime_soak_proven": False,
        "promotion_authorized": False,
    }


def main():
    try:
        result = probe()
    except (OSError, ValueError, TypeError):  # Never print upstream bodies or keys.
        print(
            json.dumps(
                {
                    "classification": "PUBLIC_SURFACE_REFUSED",
                    "promotion_authorized": False,
                }
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
