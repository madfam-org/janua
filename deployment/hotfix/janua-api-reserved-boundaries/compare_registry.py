"""Refuse a hotfix whose OAuth reservation registry is not strictly tighter.

    python compare_registry.py BASE.json NEW.json

Both files are ``dump_registry.py`` output (the JSON after ``REGISTRY=``),
taken from the image production runs (BASE) and from the hotfix image (NEW).

The hotfix may only make registration stricter:

- every public name the base module had still exists (so nothing that imports
  it on the base code breaks);
- every set may only grow: each set in this module is a reservation set, and a
  value added to one makes registering or editing a client that carries it a
  platform-admin action;
- every other value (prefixes, suffixes, first-party name prefixes, fixed
  scope/audience strings, the tenant-bound lists) is unchanged, because a
  change there can loosen authority (a new first-party prefix grants silent
  auth, for example);
- the predicates agree with the sets in the new image.

Prints the added scopes and audiences and exits 0, or prints each violation as
a GitHub ``::error::`` line and exits 1. Standard library only.
"""

from __future__ import annotations

import json
import sys


def compare(base: dict, new: dict) -> tuple[list[str], dict[str, list[str]]]:
    errors: list[str] = []
    added: dict[str, list[str]] = {}

    missing = sorted(set(base["names"]) - set(new["names"]))
    if missing:
        errors.append(f"public names removed from the registry: {missing}")

    for name, before in sorted(base["values"].items()):
        after = new["values"].get(name)
        if after is None:
            if name not in missing:
                errors.append(f"{name} is no longer a comparable value")
            continue
        if after["kind"] != before["kind"]:
            errors.append(f"{name} changed kind: {before['kind']} -> {after['kind']}")
            continue
        if before["kind"] == "set":
            lost = sorted(set(before["items"]) - set(after["items"]))
            if lost:
                errors.append(f"{name} lost values (would loosen registration): {lost}")
            gained = sorted(set(after["items"]) - set(before["items"]))
            if gained:
                added[name] = gained
        elif after != before:
            errors.append(f"{name} changed; only reservation sets may change")

    for required in ("RESERVED_SCOPES", "RESERVED_AUDIENCES", "RESERVED_CLIENT_NAMES"):
        if new["values"].get(required, {}).get("kind") != "set":
            errors.append(f"{required} is missing from the new registry")

    if new.get("self_consistent") is not True:
        errors.append("is_reserved_scope/is_reserved_audience disagree with the reserved sets")

    return errors, added


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: compare_registry.py BASE.json NEW.json", file=sys.stderr)
        return 2
    with open(argv[1]) as fh:
        base = json.load(fh)
    with open(argv[2]) as fh:
        new = json.load(fh)
    errors, added = compare(base, new)
    for error in errors:
        print(f"::error::{error}")
    if errors:
        return 1
    for name in ("RESERVED_SCOPES", "RESERVED_AUDIENCES", "RESERVED_CLIENT_NAMES"):
        print(f"{name} added: {', '.join(added.get(name, [])) or '(none)'}")
    print("Registry: strictly tighter than the base; nothing loosened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
