"""Run inside a janua-api image by the row 16 hotfix workflow (stdin of `python -`).

Prints two lines the workflow compares between the base and the hotfix:
discovery metadata (must be identical) and what the two user-facing token
grants announce as `expires_in` (a literal 3600 on the base; the minted
token's own lifetime on the hotfix).
"""

import inspect
import json

import app.main  # noqa: F401  the whole application imports
from app.core.jwt_manager import jwt_manager
from app.core.oauth_metadata import authorization_server_metadata
from app.routers.v1 import oauth_provider_grants as grants

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

print("METADATA=" + json.dumps(authorization_server_metadata(), sort_keys=True))
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
