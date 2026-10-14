"""Pure tests of app.staging_admission: target allowlist, refusals, stop-on-unknown.

The probe runs against an in-process fake of the routes it calls (an
httpx.MockTransport); the real API is exercised by running the module itself
against a local server. Nothing here opens a socket.
"""

import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlencode

import httpx
import pytest

from app import staging_admission
from app.staging_admission import AdmissionRefused, run_admission
from app.staging_synthetic import ADMISSION_CLIENT_ID, ADMISSION_REDIRECT_URI, SYNTHETIC_USERS

STEPS = [
    "operator_signin", "oauth_authorize_pkce", "oauth_code_exchange", "oauth_refresh_rotation",
    "org_create", "oauth_authorize_fresh", "org_creator_active_in_fresh_token",
    "invitation_create_without_mail", "invitee_signin", "foreign_signin",
    "foreign_accept_refused", "invitee_accept", "invitation_replay_refused",
    "invitee_active_in_fresh_token", "oauth_wrong_verifier_refused",
    "oauth_wrong_redirect_uri_refused", "oauth_code_reuse_refused",
]


@pytest.mark.parametrize("raw,expected", [
    ("http://janua-api.janua-staging.svc.cluster.local",
     ("http://janua-api.janua-staging.svc.cluster.local", "cluster")),
    ("http://janua-api.janua-staging.svc.cluster.local:8080/",
     ("http://janua-api.janua-staging.svc.cluster.local:8080", "cluster")),
    ("http://janua-api.janua-staging.svc.cluster.local:80",
     ("http://janua-api.janua-staging.svc.cluster.local:80", "cluster")),
    ("http://127.0.0.1:18080", ("http://127.0.0.1:18080", "loopback")),
    ("http://localhost:4100/", ("http://localhost:4100", "loopback")),
])
def test_staging_service_and_loopback_are_the_only_targets(raw, expected, monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert staging_admission.validate_base_url(raw) == expected


@pytest.mark.parametrize("raw", [
    "https://janua.dev", "http://janua.dev", "https://auth.madfam.io", "http://auth.madfam.io",
    "http://api.janua.dev:8080", "http://staging-auth.madfam.io",
    "https://janua-api.janua-staging.svc.cluster.local",
    "http://janua-api.janua.svc.cluster.local:8080",
    "http://janua-staging.svc.cluster.local",
    "http://a.b.janua-staging.svc.cluster.local",
    "http://janua-api.janua-staging.svc.cluster.local.evil.example",
    "http://janua-api.janua-staging.svc.cluster.local:9464",
    "http://evil.example/?h=janua-api.janua-staging.svc.cluster.local",
    "http://user:pw@127.0.0.1:8080", "http://127.0.0.1:8080/api", "http://127.0.0.1:8080?x=1",
    "http://127.0.0.1:8080#f", "http://127.0.0.2:8080", "http://[::1]:8080",
    "ftp://127.0.0.1", "", "http://127.0.0.1:99999",
])
def test_everything_else_is_refused(raw, monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with pytest.raises(AdmissionRefused):
        staging_admission.validate_base_url(raw)


def test_production_environment_refuses_even_loopback(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(AdmissionRefused) as refused:
        staging_admission.validate_base_url("http://127.0.0.1:8080")
    assert refused.value.code == "environment_production"


def passwords():
    return {user.password_env: secrets.token_urlsafe(18) + "aA1!" for user in SYNTHETIC_USERS}


@pytest.mark.parametrize("change,code", [
    ({"STAGING_INVITEE_PASSWORD": ""}, "password_missing"),
    ("drop", "password_missing"),
    ("reuse", "password_reused"),
])
def test_missing_or_reused_passwords_refuse_before_any_request(change, code, monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    env = passwords()
    if change == "drop":
        env.pop("STAGING_FOREIGN_PASSWORD")
    elif change == "reuse":
        env["STAGING_INVITEE_PASSWORD"] = env["STAGING_OPERATOR_PASSWORD"]
    else:
        env.update(change)
    calls = []
    receipt, status = run_admission("http://127.0.0.1:8080", env, httpx.MockTransport(calls.append))
    assert (status, receipt["result"], receipt["reason"]) == (2, "refused", code)
    assert calls == []


def jwt(claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"e30.{body}.c2ln"


def fail(status, message):
    return httpx.Response(status, json={"error": {"code": "HTTP_ERROR", "message": message}})


class FakeJanua:
    """Just enough of the mounted routes, holding the same invariants."""

    def __init__(self, env, **flaws):
        self.passwords = {u.email: env[u.password_env] for u in SYNTHETIC_USERS}
        self.flaws = flaws
        self.requests, self.codes, self.consented = [], {}, set()
        self.orgs, self.invitations, self.secrets_seen = {}, {}, set()

    def token(self, email, kind="access"):
        orgs = [{"id": o, "slug": s, "role": r} for (o, s, e, r) in self.orgs.values() if e == email]
        value = jwt({"sub": email.split("@")[0], "type": kind, "orgs": orgs,
                     "n": secrets.token_hex(4)})
        self.secrets_seen.add(value)
        return value

    def user(self, request):
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            return None
        sub = staging_admission._claims(header[7:])["sub"]
        return f"{sub}@staging.example.com"

    def __call__(self, request):
        self.requests.append((request.method, request.url.path, request.headers["host"]))
        key = (request.method, request.url.path)
        if key in self.flaws.get("status", {}):
            return httpx.Response(self.flaws["status"][key], json={"detail": "synthetic"})
        handler = {
            ("POST", "/api/v1/auth/signin"): self.signin,
            ("GET", "/api/v1/oauth/authorize"): self.authorize,
            ("POST", "/api/v1/oauth/consent"): self.consent,
            ("POST", "/api/v1/oauth/token"): self.token_endpoint,
            ("POST", "/api/v1/organizations/"): self.create_org,
            ("POST", "/api/v1/invitations/"): self.invite,
            ("POST", "/api/v1/invitations/accept"): self.accept,
            ("POST", "/api/v1/auth/refresh"): self.session_refresh,
        }.get(key)
        return handler(request) if handler else fail(404, "Not Found")

    def signin(self, request):
        body = json.loads(request.content)
        if self.passwords.get(body["email"]) != body["password"]:
            return fail(401, "Invalid credentials")
        return httpx.Response(200, json={"user": {}, "mfa_required": False, "tokens": {
            "access_token": self.token(body["email"]),
            "refresh_token": self.token(body["email"], "refresh"), "expires_in": 3600}})

    def issue(self, email, query):
        code = secrets.token_urlsafe(16)
        self.codes[code] = (email, query["code_challenge"][0], query["redirect_uri"][0])
        self.secrets_seen.add(code)
        target = ADMISSION_REDIRECT_URI + "?" + urlencode({"code": code, "state": query["state"][0]})
        return httpx.Response(302, headers={"location": target})

    def authorize(self, request):
        query = parse_qs(request.url.query.decode())
        email = self.user(request)
        if query["client_id"] != [ADMISSION_CLIENT_ID] or query["code_challenge_method"] != ["S256"]:
            return fail(400, "invalid_request")
        if email not in self.consented:
            self.pending = (email, query)
            return httpx.Response(200, text='<input type="hidden" name="auth_request_id" value="r1">'
                                            '<input type="hidden" name="csrf_token" value="c1">')
        return self.issue(email, query)

    def consent(self, request):
        form = parse_qs(request.content.decode())
        if form != {"auth_request_id": ["r1"], "csrf_token": ["c1"], "action": ["allow"]}:
            return fail(403, "Invalid or expired CSRF token")
        self.consented.add(self.pending[0])
        return self.issue(*self.pending)

    def token_endpoint(self, request):
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        if form["grant_type"] == "refresh_token":
            return httpx.Response(200, json={"access_token": self.token("operator@staging.example.com"),
                                             "refresh_token": self.token("operator@staging.example.com",
                                                                         "refresh"),
                                             "token_type": "Bearer"})
        if form["code"] not in self.codes:
            return fail(400, "invalid_grant: Code not found or expired")
        email, challenge, redirect = self.codes[form["code"]]
        digest = hashlib.sha256(form["code_verifier"].encode()).digest()
        verified = base64.urlsafe_b64encode(digest).rstrip(b"=").decode() == challenge
        if form["redirect_uri"] != redirect and not self.flaws.get("ignore_redirect"):
            return fail(400, "invalid_grant: redirect_uri mismatch")
        if not verified and not self.flaws.get("ignore_verifier"):
            return fail(400, "invalid_grant: PKCE verification failed")
        if not self.flaws.get("reusable_codes"):
            del self.codes[form["code"]]
        return httpx.Response(200, json={"access_token": self.token(email), "token_type": "Bearer",
                                         "refresh_token": self.token(email, "refresh"),
                                         "id_token": jwt({"sub": "x"})})

    def create_org(self, request):
        body = json.loads(request.content)
        org_id = "org-" + secrets.token_hex(4)
        self.orgs[org_id] = (org_id, body["slug"], self.user(request), "admin")
        return httpx.Response(200, json={"id": org_id, "slug": body["slug"], "name": body["name"]})

    def invite(self, request):
        body = json.loads(request.content)
        token = secrets.token_urlsafe(16)
        self.secrets_seen.add(token)
        self.invitations[token] = [body["organization_id"], body["email"], "pending"]
        return httpx.Response(201, json={
            "id": "inv-1", "organization_id": body["organization_id"], "email": body["email"],
            "status": "pending", "email_sent": False, "email_status": "unconfirmed",
            "invite_url": "https://staging-auth.madfam.io/invitations/accept?token=" + token})

    def accept(self, request):
        token = json.loads(request.content)["token"]
        org_id, email, status = self.invitations[token]
        user = self.user(request)
        if status != "pending" and not self.flaws.get("replayable"):
            return fail(400, "Invitation expired or no longer pending")
        if user != email and not self.flaws.get("accept_foreign"):
            return fail(400, "Invitation email does not match authenticated user")
        self.invitations[token][2] = "accepted"
        self.orgs[org_id + user] = (org_id, "slug", user, "member")
        return httpx.Response(200, json={"success": True, "organization_id": org_id,
                                         "user_id": "u", "message": "ok", "is_new_user": False})

    def session_refresh(self, request):
        return httpx.Response(200, json={"access_token": self.token("invitee@staging.example.com"),
                                         "refresh_token": "r2", "expires_in": 3600})


def probe(monkeypatch, **flaws):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    env = passwords()
    server = FakeJanua(env, **flaws)
    receipt, status = run_admission("http://127.0.0.1:18080", env, httpx.MockTransport(server))
    return receipt, status, server, env


def assert_secret_free(receipt, server, env):
    raw = json.dumps(receipt)
    assert "@" not in raw
    assert not any(value in raw for value in env.values())
    assert not any(value in raw for value in server.secrets_seen)
    for entry in receipt.get("steps", []):
        assert set(entry) <= {"step", "outcome", "class", "status"}


def test_every_step_passes_against_a_conforming_api(monkeypatch):
    receipt, status, server, env = probe(monkeypatch)
    assert status == 0 and receipt["result"] == "pass" and receipt["target"] == "loopback"
    assert [s["step"] for s in receipt["steps"]] == STEPS
    assert {s["outcome"] for s in receipt["steps"]} == {"pass"}
    assert {host for _, _, host in server.requests} == {"localhost"}
    assert ("POST", "/api/v1/oauth/consent", "localhost") in server.requests
    assert_secret_free(receipt, server, env)


@pytest.mark.parametrize("flaw,step", [
    ("accept_foreign", "foreign_accept_refused"),
    ("replayable", "invitation_replay_refused"),
    ("ignore_verifier", "oauth_wrong_verifier_refused"),
    ("ignore_redirect", "oauth_wrong_redirect_uri_refused"),
    ("reusable_codes", "oauth_code_reuse_refused"),
])
def test_an_accepted_negative_fails_the_run(monkeypatch, flaw, step):
    receipt, status, server, env = probe(monkeypatch, **{flaw: True})
    assert status == 1 and receipt["result"] == "fail"
    assert receipt["steps"][-1] == {"step": step, "outcome": "fail",
                                    "class": "accepted_unexpectedly", "status": 200}
    assert_secret_free(receipt, server, env)


@pytest.mark.parametrize("route,step", [
    (("POST", "/api/v1/organizations/"), "org_create"),
    (("POST", "/api/v1/invitations/"), "invitation_create_without_mail"),
    (("POST", "/api/v1/oauth/token"), "oauth_code_exchange"),
])
def test_an_unknown_response_stops_immediately_without_retry(monkeypatch, route, step):
    receipt, status, server, env = probe(monkeypatch, status={route: 500})
    assert status == 1
    assert receipt["steps"][-1] == {"step": step, "outcome": "fail",
                                    "class": "unexpected_status", "status": 500}
    assert server.requests[-1][:2] == route
    assert [r[:2] for r in server.requests].count(route) == 1
    assert_secret_free(receipt, server, env)


def test_acknowledged_mail_is_a_failure(monkeypatch):
    class Mailing(FakeJanua):
        def invite(self, request):
            response = super().invite(request)
            body = response.json() | {"email_sent": True, "email_status": "acknowledged"}
            return httpx.Response(201, json=body)

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    env = passwords()
    server = Mailing(env)
    receipt, status = run_admission("http://127.0.0.1:18080", env, httpx.MockTransport(server))
    assert status == 1
    assert receipt["steps"][-1]["step"] == "invitation_create_without_mail"
    assert_secret_free(receipt, server, env)


def test_main_prints_one_json_line(monkeypatch, capsys):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    for key in passwords():
        monkeypatch.delenv(key, raising=False)
    assert staging_admission.main(["--base-url", "https://auth.madfam.io"]) == 2
    out = capsys.readouterr().out.strip().splitlines()
    assert json.loads(out[-1]) == {"tool": "janua.staging_admission", "result": "refused",
                                   "reason": "base_url_not_allowed"}
