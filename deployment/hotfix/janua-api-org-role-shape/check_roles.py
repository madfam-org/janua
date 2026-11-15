"""Run inside an image: print what its roles claim does, for the workflow.

Runs in the base image too, which lacks the new names, so everything new is
looked up with getattr. Importing the services imports the application, so this
also proves the image imports cleanly. Nothing connects to a database.

The token is rebuilt the way the OIDC handler builds it in BOTH images
(production's handler is not part of this hotfix): the handler's own list
under ``roles``, then the shared merge's result spread over it.
"""

import json

from app.services import org_claims_service as claims
from app.services import role_service

FORGED = "example-app:admin"
GRANT = "example-app:operator"


def token_roles(handler_list, grants):
    org_claims = {claims.APP_ROLES_KEY: list(grants)} if grants else {}
    merged = claims.merge_app_roles_into_claims(org_claims, existing_roles=list(handler_list))
    return {"roles": list(handler_list), **merged}.get("roles", [])


def name_refused(name):
    check = getattr(role_service, "reject_application_role_shape", None)
    if check is None:
        return False
    try:
        check(name)
    except ValueError:
        return True
    return False


def name_allowed(name):
    check = getattr(role_service, "reject_application_role_shape", None)
    if check is None:
        return False
    try:
        check(name)
    except ValueError:
        return False
    return True


print(
    "ROLES="
    + json.dumps(
        {
            # A forged organization role, alone and next to real ones, never
            # reaches the token, even from the unpatched handler's list.
            "forged_dropped_from_token": token_roles([FORGED], [])
            == []
            and token_roles(["admin", FORGED], []) == ["admin"],
            # Bare organization roles are published as before.
            "bare_roles_published": token_roles(["admin", "member"], []) == ["admin", "member"],
            # A real grant is published, once, with or without a forged twin.
            "grant_published": token_roles(["member"], [GRANT]) == ["member", GRANT]
            and token_roles([GRANT], [GRANT]) == [GRANT],
            # Custom role names of that shape are refused; bare names are not.
            "shaped_name_refused": name_refused(FORGED),
            "bare_name_allowed": name_allowed("Support"),
        },
        sort_keys=True,
    )
)
