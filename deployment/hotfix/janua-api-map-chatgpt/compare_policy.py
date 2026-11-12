"""Refuse a hotfix whose policy is not the base plus ChatGPT on the MAP resource.

    python3 compare_policy.py BASE.json NEW.json

Exit 1 with the reasons if anything else changed. The expected delta, and only
it: on https://map.creatumundo.mx/api/mcp, the host chatgpt.com, the client id
https://chatgpt.com/oauth/client.json and the redirect
https://chatgpt.com/connector_platform_oauth_redirect are added; the CSP
redirect origins gain https://chatgpt.com; ChatGPT's published document goes
from refused to accepted as a public client; Claude's document stays accepted;
a confidential-only document stays refused.
"""

from __future__ import annotations

import json
import sys

MAP = "https://map.creatumundo.mx/api/mcp"
ADDED = {
    "cimd_hosts": ["chatgpt.com"],
    "cimd_client_ids": ["https://chatgpt.com/oauth/client.json"],
    "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
}


def compare(base: dict, new: dict) -> list[str]:
    errors: list[str] = []
    if sorted(base["resources"]) != sorted(new["resources"]):
        errors.append("the set of protected resources changed")
        return errors
    for uri in base["resources"]:
        b, n = base["resources"][uri], new["resources"][uri]
        for key in sorted(set(b) | set(n)):
            expected = b.get(key)
            if uri == MAP and key in ADDED:
                expected = sorted(set(b[key]) | set(ADDED[key]))
                if set(ADDED[key]) & set(b[key]):
                    errors.append(f"{uri} {key}: the base already has {ADDED[key]}")
            if n.get(key) != expected:
                errors.append(f"{uri} {key}: expected {expected}, got {n.get(key)}")
    origins = list(base["redirect_origins"])
    if "https://chatgpt.com" not in origins:
        origins.append("https://chatgpt.com")
    if sorted(new["redirect_origins"]) != sorted(origins):
        errors.append(
            f"redirect origins: expected {sorted(origins)}, got {sorted(new['redirect_origins'])}"
        )
    docs_b, docs_n = base["documents"], new["documents"]
    if not docs_b["chatgpt"].startswith("refused:"):
        errors.append(
            f"the base already accepts ChatGPT's document ({docs_b['chatgpt']})"
        )
    if docs_n["chatgpt"] != "accepted:none":
        errors.append(
            f"ChatGPT's document: expected accepted:none, got {docs_n['chatgpt']}"
        )
    if docs_b["claude"] != "accepted:none" or docs_n["claude"] != "accepted:none":
        errors.append(
            f"Claude's document changed: {docs_b['claude']} -> {docs_n['claude']}"
        )
    if not docs_n["confidential"].startswith("refused:"):
        errors.append(
            f"a confidential-only document is no longer refused ({docs_n['confidential']})"
        )
    return errors


def main(argv: list[str]) -> int:
    base = json.load(open(argv[1]))
    new = json.load(open(argv[2]))
    errors = compare(base, new)
    if errors:
        print("Policy: REFUSED")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Policy: the base plus ChatGPT on the MAP resource, nothing else.")
    for key, values in ADDED.items():
        print(f"  + {MAP} {key}: {', '.join(values)}")
    print("  + redirect origin: https://chatgpt.com")
    print(
        f"  ChatGPT document: {base['documents']['chatgpt']} -> {new['documents']['chatgpt']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
