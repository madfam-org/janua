"""Run inside an image: print what its registry and guest tokens do, for the workflow.

Runs in the base image too, where the new names do not exist, so they are looked
up with getattr. Importing the modules imports the application, so this also
proves the image imports cleanly. Nothing connects to a database.
"""

import json

import jwt

from app.core import reserved_oauth_boundaries as reserved
from app.routers.v1.guest import _mint_guest_jwt

PRODUCT_ROLE_SCOPES = ["tulana:operator", "nauta:platform-admin", "telesia:operator", "hcm:payroll"]
TENANT_BOUND = ["hcm:hr", "selva:infer"]
LOOK_ALIKES = ["nauta:labor-hours:read", "dhanam:cogs:read", "acme:read"]

token, _ = _mint_guest_jwt(
    guest_id="guest-hotfix-check",
    display_name="check",
    org_id="00000000-0000-0000-0000-000000000000",
    ttl_hours=1,
)
guest = jwt.decode(token, options={"verify_signature": False})

print(
    "CONTAIN="
    + json.dumps(
        {
            "product_role_scopes_reserved": all(reserved.is_reserved_scope(s) for s in PRODUCT_ROLE_SCOPES),
            "tenant_bound_registrable": not any(reserved.is_reserved_scope(s) for s in TENANT_BOUND),
            "look_alikes_unreserved": not any(reserved.is_reserved_scope(s) for s in LOOK_ALIKES),
            "guest_has_own_audience": guest.get("aud") not in (None, "janua.dev")
            and reserved.is_reserved_audience(guest.get("aud")),
            "guest_still_a_guest": guest.get("type") == "guest_access" and guest.get("roles") == ["guest"],
        },
        sort_keys=True,
    )
)
