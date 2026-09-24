"""Resend tags on every send: which app and which tenant a message belongs to.

Resend echoes a message's tags back in every webhook event for it, which is the
only way an event can be scoped to the application that sent the mail without
Janua keeping a per-message ledger. `app/services/email_events.py` reads
`source_app` and `org_id` back out of those tags; the feed filters on them.

RESEND'S TAG RULES. A tag name and value may contain only ASCII letters,
digits, underscores and dashes, at most 256 characters each; anything else is a
422 validation error, which fails the WHOLE send. Janua used to pass
`template="auth/magic-link"` and `organization="Crea Tu Mundo"` verbatim, which
Resend rejects. `sanitize_tag_value` maps every other character to `_` so a tag
can never be the reason a message is not sent.

RESERVED NAMES. `source_app`, `source_type`, `org_id` and `template` are set by
Janua from the request it authenticated. A caller-supplied tag with one of
those names is dropped, so one app cannot label its mail as another's and read
it back through the other's feed scope.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set

Tag = Dict[str, str]

_DISALLOWED = re.compile(r"[^A-Za-z0-9_-]")
MAX_TAG_LENGTH = 256

#: The source_app of mail Janua originates itself (sign-in, reset, verify...).
JANUA_SOURCE_APP = "janua"

RESERVED_TAG_NAMES = frozenset({"source_app", "source_type", "org_id", "template"})


def sanitize_tag_value(value: object) -> str:
    """`value` reduced to Resend's tag charset and length ("" if nothing is left)."""
    return _DISALLOWED.sub("_", str(value).strip())[:MAX_TAG_LENGTH]


def build_tags(
    *,
    source_app: Optional[str],
    source_type: Optional[str] = None,
    org_id: Optional[object] = None,
    template: Optional[str] = None,
    extra: Optional[Mapping[str, object]] = None,
) -> List[Tag]:
    """The Resend `tags` list for one send, reserved names first.

    `source_app` falls back to `janua` so no send is ever untagged; `org_id`
    is included only when known. Extra tags with reserved or empty names are
    dropped; empty values are dropped.
    """
    reserved = [
        ("source_app", source_app or JANUA_SOURCE_APP),
        ("source_type", source_type),
        ("org_id", org_id),
        ("template", template),
    ]
    tags: List[Tag] = []
    for name, value in reserved:
        clean = sanitize_tag_value(value) if value is not None else ""
        if clean:
            tags.append({"name": name, "value": clean})
    for name, value in (extra or {}).items():
        clean_name = sanitize_tag_value(name)
        clean_value = sanitize_tag_value(value) if value is not None else ""
        if clean_name and clean_value and clean_name not in RESERVED_TAG_NAMES:
            tags.append({"name": clean_name, "value": clean_value})
    return _dedupe(tags)


def normalize_tags(
    tags: Optional[Sequence[Mapping[str, object]]],
    *,
    default_source_app: str = JANUA_SOURCE_APP,
    org_id: Optional[object] = None,
) -> List[Tag]:
    """Sanitize an already-built `[{"name","value"}]` list for the wire.

    Used at the transport choke points, where tags arrive from many callers:
    every entry is sanitized, a missing `source_app` is filled with
    `default_source_app`, and `org_id` is added when known and absent. The
    first occurrence of a name wins, so a router's reserved tags (listed first
    by `build_tags`) cannot be overridden by a later duplicate.
    """
    cleaned: List[Tag] = []
    for entry in tags or ():
        name = sanitize_tag_value(entry.get("name", ""))
        raw = entry.get("value")
        value = sanitize_tag_value(raw) if raw is not None else ""
        if name and value:
            cleaned.append({"name": name, "value": value})
    names = {t["name"] for t in cleaned}
    head: List[Tag] = []
    if "source_app" not in names:
        head.append({"name": "source_app", "value": sanitize_tag_value(default_source_app)})
    if org_id is not None and "org_id" not in names:
        clean_org = sanitize_tag_value(org_id)
        if clean_org:
            cleaned.append({"name": "org_id", "value": clean_org})
    return _dedupe(head + cleaned)


def _dedupe(tags: Iterable[Tag]) -> List[Tag]:
    seen: Set[str] = set()
    out: List[Tag] = []
    for tag in tags:
        if tag["name"] not in seen:
            seen.add(tag["name"])
            out.append(tag)
    return out


def tag_value(tags: object, name: str) -> Optional[str]:
    """Read one tag back from a webhook payload's `data.tags`.

    Resend documents `tags` in events as an object (`{"source_app": "crea-map"}`);
    the send API takes a list of `{"name", "value"}`. Both shapes are accepted
    so a provider-side format change degrades to "no tag", never to an error.
    """
    raw: object = None
    if isinstance(tags, Mapping):
        raw = tags.get(name)
    elif isinstance(tags, list):
        for entry in tags:
            if isinstance(entry, Mapping) and entry.get("name") == name:
                raw = entry.get("value")
                break
    if raw is None:
        return None
    clean = sanitize_tag_value(raw)[:64]
    return clean or None
