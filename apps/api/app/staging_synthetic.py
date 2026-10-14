"""Fixed synthetic identities shared by the staging seed and the admission probe.

Constants only: no settings, no database, no network. Every value here is
synthetic (``example.com`` is reserved by RFC 2606) and exists only in the
isolated staging database; nothing in this module is a credential.
"""

from typing import NamedTuple


class SyntheticUser(NamedTuple):
    role: str
    email: str
    password_env: str


SYNTHETIC_USERS = (
    SyntheticUser("operator", "operator@staging.example.com", "STAGING_OPERATOR_PASSWORD"),
    SyntheticUser("invitee", "invitee@staging.example.com", "STAGING_INVITEE_PASSWORD"),
    SyntheticUser("foreign", "foreign@staging.example.com", "STAGING_FOREIGN_PASSWORD"),
)

# One public (no secret) PKCE client. The redirect URI is a loopback path no
# one listens on: the probe reads the 302 Location and never follows it.
ADMISSION_CLIENT_ID = "jnc_staging-admission-probe"
ADMISSION_CLIENT_NAME = "staging-admission-probe"
ADMISSION_REDIRECT_URI = "http://127.0.0.1/admission-callback"
ADMISSION_SCOPES = ("openid", "profile", "email")
ADMISSION_GRANT_TYPES = ("authorization_code", "refresh_token")
