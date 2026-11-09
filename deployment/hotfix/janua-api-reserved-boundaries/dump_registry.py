"""Print the OAuth reservation registry an image actually loads, as one JSON line.

Run INSIDE an image, piped on stdin (no volume mount, so it also works on
runners where Docker is remote):

    docker run --rm -i --entrypoint python <env> IMAGE - < dump_registry.py

Importing ``app.core`` imports the whole application (``app/__init__.py``), so
a clean run also proves the image starts importing with the copied files.
Only public reservation values are printed: scope, audience and client-name
strings that are already in the public source. No configuration, secret or
database value is read.
"""

from __future__ import annotations

import json
from types import ModuleType


def encode(value):
    """A JSON form for the values that carry authority; None for everything else."""
    if isinstance(value, (frozenset, set)):
        return {"kind": "set", "items": sorted(str(item) for item in value)}
    if isinstance(value, (tuple, list)):
        return {"kind": "seq", "items": [str(item) for item in value]}
    if isinstance(value, str):
        return {"kind": "str", "value": value}
    if isinstance(value, dict):
        return {"kind": "keys", "items": sorted(str(key) for key in value)}
    return None


def snapshot(module: ModuleType) -> dict:
    names = sorted(name for name in dir(module) if not name.startswith("_"))
    values = {}
    for name in names:
        encoded = encode(getattr(module, name))
        if encoded is not None:
            values[name] = encoded
    # The predicates the registration check calls must agree with the sets.
    consistent = all(module.is_reserved_scope(s) for s in module.RESERVED_SCOPES) and all(
        module.is_reserved_audience(a) for a in module.RESERVED_AUDIENCES
    )
    return {"names": names, "values": values, "self_consistent": consistent}


if __name__ == "__main__":
    # The registration check is the enforcement point that reads the registry.
    import app.services.oauth_client_authority  # noqa: F401
    from app.core import reserved_oauth_boundaries

    print("REGISTRY=" + json.dumps(snapshot(reserved_oauth_boundaries), sort_keys=True))
