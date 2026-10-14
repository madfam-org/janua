"""Synthetic admission probe against the real staging API, over plain HTTP.

    python -m app.staging_admission --base-url http://janua-api.janua-staging.svc.cluster.local

Uses only the identities ``python -m app.staging_seed`` created and their
passwords from the environment. No database access, no mail, no retries.

Flow: operator signs in; authorization code with PKCE (S256) for the seeded
public client; code exchange; one refresh rotation; the operator creates an
organization and a freshly minted token lists it with the creator's active
admin role; the operator invites the invitee (token read from the response's
``invite_url``; mail must not be acknowledged); a foreign user's acceptance is
refused; the invitee accepts; a replay is refused; a fresh invitee token lists
the active membership; a wrong ``code_verifier``, a wrong ``redirect_uri`` and
a consumed code are refused.

Every non-idempotent step stops the run at the first unexpected response.
Output is one bounded JSON line of step names and classifications: never
tokens, passwords, codes, emails or response bodies. Exit 0 only when every
step passed, 1 on any failure (including a negative that was accepted), 2
when the configuration is refused before any request.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sys
from typing import Callable, Mapping, Optional
from urllib.parse import parse_qs, urlsplit

import httpx

from app.staging_synthetic import (
    ADMISSION_CLIENT_ID,
    ADMISSION_REDIRECT_URI,
    ADMISSION_SCOPES,
    SYNTHETIC_USERS,
)

CLUSTER_HOST_SUFFIX = ".janua-staging.svc.cluster.local"
CLUSTER_PORTS = frozenset({None, 80, 8080})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})
# TrustedHostMiddleware (app/main.py) does not list the staging Service name;
# the staging Deployment's own probes send this same Host header.
HOST_HEADER = "localhost"
WRONG_REDIRECT_URI = ADMISSION_REDIRECT_URI + "-other"
_DNS_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_HIDDEN = {
    name: re.compile(rf'name="{name}" value="([A-Za-z0-9_-]+)"')
    for name in ("auth_request_id", "csrf_token")
}


class AdmissionRefused(Exception):
    """Configuration refused before any request; ``code`` is a fixed identifier."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class StepFailed(Exception):
    def __init__(self, classification: str, status: Optional[int] = None):
        super().__init__(classification)
        self.classification = classification
        self.status = status


def validate_base_url(raw: str) -> tuple[str, str]:
    """Only the staging Service (any port the Service or pod exposes) or loopback."""
    if os.environ.get("ENVIRONMENT") == "production":
        raise AdmissionRefused("environment_production")
    try:
        parts = urlsplit(raw or "")
        port = parts.port
    except ValueError as exc:
        raise AdmissionRefused("base_url_invalid") from exc
    host = (parts.hostname or "").lower()
    if (
        parts.scheme != "http"
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or parts.path not in ("", "/")
    ):
        raise AdmissionRefused("base_url_not_allowed")
    if host in LOOPBACK_HOSTS:
        return f"http://{host}" + (f":{port}" if port else ""), "loopback"
    service = host[: -len(CLUSTER_HOST_SUFFIX)] if host.endswith(CLUSTER_HOST_SUFFIX) else ""
    if _DNS_LABEL.match(service) and port in CLUSTER_PORTS:
        return f"http://{host}" + (f":{port}" if port else ""), "cluster"
    raise AdmissionRefused("base_url_not_allowed")


def read_passwords(environ: Mapping[str, str]) -> dict[str, str]:
    passwords = {user.role: environ.get(user.password_env) or "" for user in SYNTHETIC_USERS}
    if not all(passwords.values()):
        raise AdmissionRefused("password_missing")
    if len(set(passwords.values())) != len(passwords):
        raise AdmissionRefused("password_reused")
    return passwords


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _claims(token: str) -> dict:
    """The payload as received from the token endpoint; presence checks only."""
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def _error_text(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or "")
    if isinstance(error, str):
        return error
    detail = body.get("detail")
    return detail if isinstance(detail, str) else ""


def _expect(response: httpx.Response, status: int) -> dict:
    if response.status_code != status:
        raise StepFailed("unexpected_status", response.status_code)
    body = response.json()
    if not isinstance(body, dict):
        raise StepFailed("unexpected_body", response.status_code)
    return body


def _refused(response: httpx.Response, status: int, prefix: str = "") -> None:
    if response.is_success:
        raise StepFailed("accepted_unexpectedly", response.status_code)
    if response.status_code != status:
        raise StepFailed("unexpected_status", response.status_code)
    if prefix and not _error_text(response).startswith(prefix):
        raise StepFailed("unexpected_refusal", response.status_code)


def _has_org(token: str, org_id: str, role: str) -> bool:
    orgs = _claims(token).get("orgs") or []
    return any(o.get("id") == org_id and o.get("role") == role for o in orgs)


class Admission:
    def __init__(self, http: httpx.Client, passwords: Mapping[str, str]):
        self.http = http
        self.passwords = passwords
        self.emails = {user.role: user.email for user in SYNTHETIC_USERS}
        self.steps: list[dict] = []

    def step(self, name: str, action: Callable[[], object]):
        try:
            value = action()
        except StepFailed as exc:
            self._record(name, exc.classification, exc.status)
            raise
        except httpx.HTTPError as exc:
            self._record(name, "transport_error")
            raise StepFailed("transport_error") from exc
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            self._record(name, "unexpected_body")
            raise StepFailed("unexpected_body") from exc
        except Exception as exc:  # Fail closed with a receipt, never a traceback with data.
            self._record(name, "unexpected_error")
            raise StepFailed("unexpected_error") from exc
        self.steps.append({"step": name, "outcome": "pass"})
        return value

    def _record(self, name: str, classification: str, status: Optional[int] = None):
        entry = {"step": name, "outcome": "fail", "class": classification}
        if status is not None:
            entry["status"] = int(status)
        self.steps.append(entry)

    # --- HTTP flows ---------------------------------------------------------

    def signin(self, role: str) -> dict:
        body = _expect(self.http.post("/api/v1/auth/signin", json={
            "email": self.emails[role], "password": self.passwords[role],
        }), 200)
        if body.get("mfa_required") or not body["tokens"]["access_token"]:
            raise StepFailed("unexpected_body", 200)
        return body["tokens"]

    def authorize(self, session: dict) -> tuple[str, str]:
        verifier, challenge = _pkce()
        state = secrets.token_urlsafe(16)
        bearer = _bearer(session)
        response = self.http.get("/api/v1/oauth/authorize", headers=bearer, params={
            "response_type": "code", "client_id": ADMISSION_CLIENT_ID,
            "redirect_uri": ADMISSION_REDIRECT_URI, "scope": " ".join(ADMISSION_SCOPES),
            "state": state, "nonce": secrets.token_urlsafe(16),
            "code_challenge": challenge, "code_challenge_method": "S256",
        })
        if response.status_code == 200:  # First run: this client has no consent yet.
            fields = {k: p.search(response.text) for k, p in _HIDDEN.items()}
            if not all(fields.values()):
                raise StepFailed("unexpected_body", 200)
            response = self.http.post("/api/v1/oauth/consent", headers=bearer, data={
                **{k: m.group(1) for k, m in fields.items()}, "action": "allow",
            })
        if response.status_code != 302:
            raise StepFailed("unexpected_status", response.status_code)
        callback = urlsplit(response.headers["location"])
        query = parse_qs(callback.query)
        if (
            f"{callback.scheme}://{callback.netloc}{callback.path}" != ADMISSION_REDIRECT_URI
            or query.get("state") != [state]
            or "error" in query
            or len(query.get("code", [])) != 1
        ):
            raise StepFailed("unexpected_redirect", 302)
        return query["code"][0], verifier

    def exchange(self, code: str, verifier: str, redirect_uri: str = ADMISSION_REDIRECT_URI):
        return self.http.post("/api/v1/oauth/token", data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
            "client_id": ADMISSION_CLIENT_ID, "code_verifier": verifier,
        })

    def tokens(self, response: httpx.Response, id_token: bool = True) -> dict:
        body = _expect(response, 200)
        if (
            not body.get("access_token")
            or not body.get("refresh_token")
            or (id_token and not body.get("id_token"))
        ):
            raise StepFailed("unexpected_body", 200)
        _claims(body["access_token"])
        return body

    def refresh(self, grant: dict) -> dict:
        body = self.tokens(self.http.post("/api/v1/oauth/token", data={
            "grant_type": "refresh_token", "refresh_token": grant["refresh_token"],
            "client_id": ADMISSION_CLIENT_ID,
        }), id_token=False)
        if (
            body["refresh_token"] == grant["refresh_token"]
            or _claims(body["access_token"])["sub"] != _claims(grant["access_token"])["sub"]
        ):
            raise StepFailed("rotation_missing", 200)
        return body

    def create_org(self, session: dict) -> dict:
        slug = "admision-sintetica-" + secrets.token_hex(6)
        body = _expect(self.http.post(
            "/api/v1/organizations/", headers=_bearer(session),
            json={"name": "Admisión sintética " + slug[-12:], "slug": slug},
        ), 200)
        if body.get("slug") != slug or not body.get("id"):
            raise StepFailed("unexpected_body", 200)
        return body

    def invite(self, session: dict, org_id: str) -> str:
        body = _expect(self.http.post("/api/v1/invitations/", headers=_bearer(session), json={
            "organization_id": org_id, "email": self.emails["invitee"], "role": "member",
        }), 201)
        if (
            body.get("organization_id") != org_id
            or body.get("status") != "pending"
            or body.get("email_sent") is not False
            or body.get("email_status") == "acknowledged"
        ):
            raise StepFailed("unexpected_body", 201)
        tokens = parse_qs(urlsplit(body["invite_url"]).query).get("token", [])
        if len(tokens) != 1 or not tokens[0]:
            raise StepFailed("unexpected_body", 201)
        return tokens[0]

    def accept(self, session: dict, token: str) -> httpx.Response:
        return self.http.post(
            "/api/v1/invitations/accept", headers=_bearer(session), json={"token": token}
        )

    # --- The run ------------------------------------------------------------

    def run(self) -> None:
        step = self.step
        operator = step("operator_signin", lambda: self.signin("operator"))
        code, verifier = step("oauth_authorize_pkce", lambda: self.authorize(operator))
        grant = step("oauth_code_exchange", lambda: self.tokens(self.exchange(code, verifier)))
        step("oauth_refresh_rotation", lambda: self.refresh(grant))

        org = step("org_create", lambda: self.create_org(operator))
        fresh_code, fresh_verifier = step("oauth_authorize_fresh", lambda: self.authorize(operator))

        def creator_claim():
            fresh = self.tokens(self.exchange(fresh_code, fresh_verifier))
            if not _has_org(fresh["access_token"], org["id"], "admin"):
                raise StepFailed("membership_missing", 200)

        step("org_creator_active_in_fresh_token", creator_claim)

        token = step("invitation_create_without_mail", lambda: self.invite(operator, org["id"]))
        invitee = step("invitee_signin", lambda: self.signin("invitee"))
        foreign = step("foreign_signin", lambda: self.signin("foreign"))
        step("foreign_accept_refused", lambda: _refused(self.accept(foreign, token), 400))

        def invitee_accept():
            body = _expect(self.accept(invitee, token), 200)
            if body.get("success") is not True or body.get("organization_id") != org["id"]:
                raise StepFailed("unexpected_body", 200)

        step("invitee_accept", invitee_accept)
        step("invitation_replay_refused", lambda: _refused(self.accept(invitee, token), 400))

        def invitee_membership():
            fresh = self.tokens(self.http.post(
                "/api/v1/auth/refresh", json={"refresh_token": invitee["refresh_token"]},
            ), id_token=False)
            if not _has_org(fresh["access_token"], org["id"], "member"):
                raise StepFailed("membership_missing", 200)

        step("invitee_active_in_fresh_token", invitee_membership)

        def wrong_verifier():
            code, _ = self.authorize(operator)
            _refused(self.exchange(code, _pkce()[0]), 400, "invalid_grant")

        def wrong_redirect():
            code, verifier = self.authorize(operator)
            _refused(self.exchange(code, verifier, WRONG_REDIRECT_URI), 400, "invalid_grant")

        step("oauth_wrong_verifier_refused", wrong_verifier)
        step("oauth_wrong_redirect_uri_refused", wrong_redirect)
        step("oauth_code_reuse_refused",
             lambda: _refused(self.exchange(fresh_code, fresh_verifier), 400, "invalid_grant"))


def _bearer(session: dict) -> dict:
    return {"Authorization": "Bearer " + session["access_token"]}


def run_admission(
    base_url: str,
    environ: Mapping[str, str],
    transport: Optional[httpx.BaseTransport] = None,
) -> tuple[dict, int]:
    receipt: dict = {"tool": "janua.staging_admission"}
    try:
        base, target = validate_base_url(base_url)
        passwords = read_passwords(environ)
    except AdmissionRefused as exc:
        return {**receipt, "result": "refused", "reason": exc.code}, 2
    receipt["target"] = target
    with httpx.Client(
        base_url=base, transport=transport, follow_redirects=False, trust_env=False,
        timeout=httpx.Timeout(15.0), headers={"Host": HOST_HEADER},
    ) as http:
        admission = Admission(http, passwords)
        try:
            admission.run()
            status = 0
        except StepFailed:
            status = 1
    receipt.update(result="pass" if status == 0 else "fail", steps=admission.steps)
    return receipt, status


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.staging_admission")
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args(argv)
    receipt, status = run_admission(args.base_url, os.environ)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return status


if __name__ == "__main__":
    sys.exit(main())
