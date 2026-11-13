"""Run inside an image: print what its login code exposes, for the workflow.

Importing the auth modules imports the application, so this also proves the
image imports cleanly. Nothing connects to a database.
"""

import inspect
import json

from app.auth import hosted_security, tenant_login_context as t

source = inspect.getsource(hosted_security)
print(
    "LOGIN="
    + json.dumps(
        {
            "platform_fallback": hasattr(t, "_platform_member_by_email"),
            "client_pool_rule": hasattr(t, "user_in_client_pool"),
            "membership_gate": hasattr(t, "require_client_membership"),
            "security_uses_client_pool_rule": "user_in_client_pool" in source,
        },
        sort_keys=True,
    )
)
