"""First-party open/click measurement: Janua measures, Resend does not.

WHY THIS EXISTS (owner decision 2026-09-25). Resend's open/click tracking is a
per-DOMAIN switch. Turning it on for `creatumundo.mx` would force every
token-bearing message from that domain (the branded sign-in email) to go out
TEXT-ONLY (see app/services/email_tracking.py). The owner wants both: login mail
branded and never measured, and money mail (MAP's monthly billing notice) fully
measured. So Resend tracking stays OFF and `EMAIL_TRACKED_SENDER_DOMAINS` stays
empty; Janua instruments the individual messages a caller opts in, on a tracking
host that lives on the TENANT's own domain (`CTM_TRACKING_HOST`).

WHEN A MESSAGE IS INSTRUMENTED. All of these, or it is sent unmodified and the
reason is logged:

  1. the caller asked (`track_engagement: true` on /internal/email/send);
  2. it is not token mail: the caller did not set `contains_token_link`, and the
     credential-link detector (`email_tracking.html_carries_token_link`) finds
     nothing in its HTML;
  3. it still has an HTML part on the wire;
  4. the resolved sender binding has a tracking origin, and that origin's host
     is on the domain of the From address actually used (so a CTM message that
     fell back to `hola@madfam.io` is never measured through a CTM host, and a
     misconfigured `*.madfam.io` origin can never appear on CTM mail).

WHAT INSTRUMENTING DOES (HTML part only; the text part is never touched).
One opaque token per message (256-bit, `secrets.token_urlsafe(32)`), stored only
as its SHA-256. Every http(s) `<a href>` not already on the tracking host becomes
`{origin}/e/c/{token}/{i}`; `mailto:`, `tel:` and every other scheme are left
alone. A 1x1 pixel `{origin}/e/o/{token}.gif` (empty alt, zero border) goes
before `</body>`. The ORIGINAL targets are stored server-side
(`email_tracking_links`), so a click is always redirected to the stored target
by index — never to anything taken from the request. The token row is written
BEFORE the send (a failure there sends the message unmodified), and bound to
Resend's `email_id` right after, so first-party events join the same message as
webhook events in the per-app feed.

WHAT AN EVENT STORES. The same minimized row as a webhook event
(`email_events`, `source='first_party'`): message id, `email.opened` /
`email.clicked`, when, source_app/org_id, and for a click the target reduced by
`email_events.sanitize_click_link`. Never the IP, never the user agent: those are
read in memory only, to set the coarse `possible_prefetch` flag. Deduped by a
deterministic key: one open per message, one click per link — plus, separately,
the first hit that looked automatic, so an Apple Mail prefetch cannot hide the
person's own open.
"""

from __future__ import annotations

import base64
import hashlib
import html as html_lib
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_event import EmailTrackingLink
from app.services.email_events import ParsedEvent, record_event, sanitize_click_link
from app.services.email_tags import tag_value
from app.services.email_tracking import html_carries_token_link
from app.services.sender_binding import (
    PLATFORM_BINDING,
    PLATFORM_TENANT,
    SenderBinding,
    tracking_bindings,
    tracking_host_for,
)

logger = structlog.get_logger()

OPEN_PREFIX = "/e/o/"
CLICK_PREFIX = "/e/c/"
SOURCE_FIRST_PARTY = "first_party"

#: `secrets.token_urlsafe(32)` always yields 43 base64url characters.
TOKEN_BYTES = 32
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
INDEX_PATTERN = re.compile(r"^(0|[1-9][0-9]{0,2})$")
#: Links beyond this many are left as they are (and so are not measured).
MAX_LINKS = 200

#: The transparent 1x1 GIF every pixel request gets, whatever the token.
PIXEL_GIF = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")

_A_TAG = re.compile(r"<a\b[^>]*>", re.IGNORECASE)
_HREF = re.compile(r"""(\bhref\s*=\s*)(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""", re.IGNORECASE)
_BODY_CLOSE = re.compile(r"</body\s*>", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def new_token() -> Tuple[str, str]:
    """(token, sha256 hex) — the token goes in the URLs, only the hash is stored."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def cuenta_for(binding: SenderBinding) -> str:
    """The Resend account slug `email_events.cuenta` uses for this binding."""
    return "platform" if binding.tenant == PLATFORM_TENANT else binding.tenant


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------


def _host_within(host: str, domain: str) -> bool:
    return bool(domain) and (host == domain or host.endswith("." + domain))


def engagement_decision(
    *,
    requested: bool,
    html: Optional[str],
    token_link: bool,
    binding: SenderBinding,
    sender_address: str,
) -> Tuple[Optional[str], str]:
    """(tracking origin, reason). The origin is None unless every rule holds."""
    if not requested:
        return None, "not_requested"
    if token_link:
        return None, "token_link_declared"
    if not html or not html.strip():
        return None, "no_html"
    if html_carries_token_link(html):
        return None, "credential_link_detected"
    origin = tracking_host_for(binding)
    if origin is None:
        return None, "no_tracking_host"
    sender_domain = sender_address.rsplit("@", 1)[-1].strip().strip(">").lower()
    if not _host_within(origin.removeprefix("https://"), sender_domain):
        return None, "tracking_host_not_on_sender_domain"
    return origin, "instrumented"


# ---------------------------------------------------------------------------
# The rewrite (pure)
# ---------------------------------------------------------------------------


def _trackable(url: str, tracking_host: str) -> bool:
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    if parts.scheme.lower() not in {"http", "https"} or not host:
        return False
    return host.lower() != tracking_host


def open_url(origin: str, token: str) -> str:
    return f"{origin}{OPEN_PREFIX}{token}.gif"


def click_url(origin: str, token: str, index: int) -> str:
    return f"{origin}{CLICK_PREFIX}{token}/{index}"


def pixel_tag(origin: str, token: str) -> str:
    return (
        f'<img src="{open_url(origin, token)}" width="1" height="1" alt="" border="0" '
        'style="display:block;border:0;width:1px;height:1px">'
    )


def instrument_html(html: str, origin: str, token: str) -> Tuple[str, List[str]]:
    """(instrumented HTML, original link targets by index).

    Only the `href` of `<a>` tags is rewritten; the attribute value is replaced
    by a URL made only of URL-safe characters, so no escaping can break. The
    stored target is the href as the reader's client would resolve it (HTML
    entities decoded, e.g. `&amp;` -> `&`).
    """
    tracking_host = origin.removeprefix("https://")
    links: List[str] = []

    def rewrite(match: re.Match[str]) -> str:
        tag = match.group(0)
        href = _HREF.search(tag)
        if href is None or len(links) >= MAX_LINKS:
            return tag
        raw = next((g for g in href.groups()[1:] if g is not None), "")
        target = html_lib.unescape(raw).strip()
        if not _trackable(target, tracking_host):
            return tag
        index = len(links)
        links.append(target)
        replacement = f'{href.group(1)}"{click_url(origin, token, index)}"'
        return tag[: href.start()] + replacement + tag[href.end() :]

    body = _A_TAG.sub(rewrite, html)
    closes = list(_BODY_CLOSE.finditer(body))
    pixel = pixel_tag(origin, token)
    if closes:
        at = closes[-1].start()
        body = body[:at] + pixel + body[at:]
    else:
        body = body + pixel
    return body, links


# ---------------------------------------------------------------------------
# The send side
# ---------------------------------------------------------------------------

#: Where the send path gets a DB session (it has none of its own). Tests point
#: this at their scratch database.
SessionFactory = Callable[[], Any]
session_factory: Optional[SessionFactory] = None


def _factory() -> SessionFactory:
    if session_factory is not None:
        return session_factory
    from app.database import AsyncSessionLocal

    return AsyncSessionLocal


@dataclass(frozen=True)
class PreparedEngagement:
    html: str
    token_hash: str
    link_count: int


async def prepare_engagement(
    *,
    requested: bool,
    html: Optional[str],
    token_link: bool,
    binding: SenderBinding,
    sender_address: str,
    tags: Sequence[Mapping[str, object]],
    message_id: Optional[str] = None,
) -> Optional[PreparedEngagement]:
    """Instrument one message and store its token row, or None (send it as is).

    Never raises: measurement must not be the reason a message is not sent.
    """
    origin, reason = engagement_decision(
        requested=requested,
        html=html,
        token_link=token_link,
        binding=binding,
        sender_address=sender_address,
    )
    if origin is None:
        if requested:
            logger.info("email.engagement_not_instrumented", reason=reason, message_id=message_id)
        return None
    assert html is not None  # engagement_decision refuses an empty body
    token, token_hash = new_token()
    instrumented, links = instrument_html(html, origin, token)
    try:
        async with _factory()() as session:
            session.add(
                EmailTrackingLink(
                    token_hash=token_hash,
                    cuenta=cuenta_for(binding),
                    source_app=tag_value(tags, "source_app"),
                    org_id=tag_value(tags, "org_id"),
                    email_id=None,
                    links=json.dumps(links),
                    created_at=datetime.utcnow(),
                )
            )
            await session.commit()
    except Exception as exc:  # the message still goes out, unmeasured
        logger.error(
            "email.engagement_store_failed_sending_unmodified",
            error_type=type(exc).__name__,
            message_id=message_id,
        )
        return None
    logger.info("email.engagement_instrumented", links=len(links), message_id=message_id)
    return PreparedEngagement(html=instrumented, token_hash=token_hash, link_count=len(links))


async def bind_email_id(token_hash: str, email_id: str) -> bool:
    """Attach Resend's message id to the token row. Never raises.

    Without it clicks still redirect correctly; only the events cannot be
    attributed, and are then not recorded.
    """
    try:
        async with _factory()() as session:
            await session.execute(
                update(EmailTrackingLink)
                .where(EmailTrackingLink.token_hash == token_hash)
                .where(EmailTrackingLink.email_id.is_(None))
                .values(email_id=email_id[:255])
            )
            await session.commit()
        return True
    except Exception as exc:
        logger.error("email.engagement_bind_failed", error_type=type(exc).__name__)
        return False


# ---------------------------------------------------------------------------
# The public side
# ---------------------------------------------------------------------------


def fallback_site(host_header: Optional[str]) -> str:
    """Where an unresolvable link goes: decided by the request Host ALONE.

    An unknown token and a known token with a bad index on the same host get
    the same answer, so the redirect says nothing about validity.
    """
    host = (host_header or "").split(",")[0].strip().lower()
    host = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    binding = tracking_bindings().get(host)
    return binding.default_site if binding is not None else PLATFORM_BINDING.default_site


async def find_link(db: AsyncSession, token: str) -> Optional[EmailTrackingLink]:
    """The token's row, or None. A malformed token never reaches the database."""
    if not TOKEN_PATTERN.match(token or ""):
        return None
    result = await db.execute(
        select(EmailTrackingLink).where(EmailTrackingLink.token_hash == hash_token(token))
    )
    return result.scalar_one_or_none()


def stored_target(link: EmailTrackingLink, index: str) -> Optional[str]:
    """The stored target at `index`, or None. Only http(s) ever comes back."""
    if not INDEX_PATTERN.match(index or ""):
        return None
    try:
        targets = json.loads(str(link.links))
    except (TypeError, ValueError):
        return None
    position = int(index)
    if not isinstance(targets, list) or position >= len(targets):
        return None
    target = targets[position]
    if not isinstance(target, str):
        return None
    try:
        scheme = urlsplit(target).scheme.lower()
    except ValueError:
        return None
    return target if scheme in {"http", "https"} else None


#: A User-Agent that is exactly this is Apple Mail Privacy Protection's proxy.
_APPLE_MPP_UA = "mozilla/5.0"
_SCANNER_MARKERS = (
    "bot",
    "crawler",
    "spider",
    "scanner",
    "barracuda",
    "mimecast",
    "proofpoint",
    "messagelabs",
    "symantec",
    "trendmicro",
    "forcepoint",
    "safelinks",
    "safe links",
    "python-",
    "curl/",
    "wget/",
    "go-http-client",
    "java/",
    "okhttp",
    "headlesschrome",
    "phantomjs",
    "libwww",
)
#: A hit this soon after the message was stored is almost never a person.
PREFETCH_WINDOW_SECONDS = 15


def possible_prefetch(
    *,
    method: str,
    user_agent: Optional[str],
    purpose: Optional[str],
    seconds_since_send: Optional[float],
) -> bool:
    """Coarse: did an image proxy or a link scanner, not a person, make this hit?

    Reads the request in memory; nothing here is ever stored except the answer.
    """
    if method.upper() == "HEAD":
        return True
    if purpose and "prefetch" in purpose.lower():
        return True
    ua = (user_agent or "").strip().lower()
    if not ua or ua == _APPLE_MPP_UA:
        return True
    if any(marker in ua for marker in _SCANNER_MARKERS):
        return True
    return seconds_since_send is not None and 0 <= seconds_since_send < PREFETCH_WINDOW_SECONDS


class _Throttle:
    """Per-process: at most one write attempt per key per window (bounded memory).

    The database already dedupes (ON CONFLICT DO NOTHING on a deterministic
    key); this only stops a scanner hammering one URL from hammering Postgres.
    """

    def __init__(self, window_seconds: float = 600.0, max_keys: int = 20_000) -> None:
        self.window = window_seconds
        self.max_keys = max_keys
        self._seen: Dict[str, float] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: Optional[float] = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            last = self._seen.get(key)
            if last is not None and current - last < self.window:
                return False
            if len(self._seen) >= self.max_keys:
                cutoff = current - self.window
                self._seen = {k: v for k, v in self._seen.items() if v >= cutoff}
                if len(self._seen) >= self.max_keys:
                    self._seen.clear()
            self._seen[key] = current
            return True

    def reset(self) -> None:
        with self._lock:
            self._seen.clear()


throttle = _Throttle()


def dedupe_key(token_hash: str, kind: str, index: Optional[int], prefetch: bool) -> str:
    """The `svix_id` of a first-party event: one per (message, kind, link, class)."""
    tail = "" if index is None else f":{index}"
    return f"fp:{kind}{'p' if prefetch else ''}:{token_hash}{tail}"


async def record_hit(
    db: AsyncSession,
    link: EmailTrackingLink,
    *,
    kind: str,
    index: Optional[int],
    prefetch: bool,
    target: Optional[str] = None,
) -> bool:
    """Store one first-party open ('o') or click ('c'). True if a row was added.

    Nothing is written for a message whose Resend id was never bound (it could
    not be joined to anything in the feed), nor for a repeat inside the
    throttle window, nor for a repeat of the same (kind, link, class) ever.
    """
    email_id: Optional[str] = link.email_id  # type: ignore[assignment]
    if not email_id:
        return False
    key = dedupe_key(str(link.token_hash), kind, index, prefetch)
    if not throttle.allow(key):
        return False
    event = ParsedEvent(
        email_id=email_id,
        event_type="email.opened" if kind == "o" else "email.clicked",
        occurred_at=datetime.utcnow(),
        source_app=link.source_app,  # type: ignore[arg-type]
        org_id=link.org_id,  # type: ignore[arg-type]
        click_link=sanitize_click_link(target) if kind == "c" else None,
    )
    return await record_event(
        db,
        str(link.cuenta),
        key,
        event,
        source=SOURCE_FIRST_PARTY,
        possible_prefetch=prefetch,
    )
