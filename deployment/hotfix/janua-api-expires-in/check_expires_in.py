"""Run inside a janua-api image by the row 16 hotfix workflow (stdin of `python -`).

Prints two lines the workflow compares between the base and the hotfix:

- DISCOVERY: the discovery document still builds, and the module that builds
  it does not name the one module this row changes. The workflow has already
  proven every other file byte-identical, so discovery cannot differ. The
  document itself is never printed.
- EXPIRES_IN: what the two user-facing token grants announce (a literal 3600
  on the base; the minted token's own lifetime on the hotfix).
"""

import inspect
import json

import app.main as application  # the whole application imports
from app.core import oauth_metadata
from app.core.jwt_manager import jwt_manager
from app.routers.v1 import oauth_provider_grants as grants

assert application.app is not None

discovery_builds = "issuer" in oauth_metadata.authorization_server_metadata()
names_the_module = "oauth_provider_grants" in inspect.getsource(oauth_metadata)

source = inspect.getsource(grants._handle_authorization_code_grant) + inspect.getsource(
    grants._handle_refresh_token_grant
)
helper = getattr(grants, "_access_token_expires_in", None)
minted_matches_exp = None
if helper is not None:
    _token, _jti, expires_at = jwt_manager.create_access_token(
        "hotfix-verification", "verification@example.invalid"
    )
    lifetime = jwt_manager.access_token_expire_minutes * 60
    minted_matches_exp = lifetime - 2 <= helper(expires_at) <= lifetime and lifetime != 3600

print(
    "DISCOVERY="
    + json.dumps({"builds": discovery_builds, "names_the_module": names_the_module}, sort_keys=True)
)
print(
    "EXPIRES_IN="
    + json.dumps(
        {
            "helper": source.count("expires_in=_access_token_expires_in(access_expires_at)"),
            "literal_3600": source.count("expires_in=3600"),
            "minted_matches_exp": minted_matches_exp,
        },
        sort_keys=True,
    )
)
