"""Token links must never pass through Resend's click/open tracking.

Resend's open and click tracking are per-DOMAIN settings. When they are on,
Resend rewrites every link in the message's HTML part to go through its own
redirector, and injects a tracking pixel into that HTML. It never touches a
text/plain part. Resend's own guidance is not to track transactional mail and
it warns that link rewriting can break verification links.

For a message carrying a one-time or signed token (a magic link, a password
reset, an email verification, an invitation, recovery codes) that rewrite is
not an analytics detail: it routes the credential through a third-party URL,
and a mail scanner that pre-fetches the rewritten link can burn a single-use
token before the person ever clicks. So the rule is simple and has no
exceptions:

    token-bearing message  AND  From domain in EMAIL_TRACKED_SENDER_DOMAINS
        -> send it TEXT-ONLY (the HTML part is dropped; the text part is kept,
           or derived from the HTML when the caller only wrote HTML).

A message is token-bearing when its caller says so (every template that
embeds a token passes `token_link=True`), or when its HTML contains a link
whose query or fragment carries a credential-looking parameter (`token`,
`code`, `signature`, ...). The detector is a backstop for callers that forget,
not the primary mechanism: it can only ever make a message MORE conservative.

Outside a tracked domain nothing changes: HTML mail stays HTML.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import List, Optional, Tuple
from urllib.parse import parse_qsl, urlsplit

from app.config import settings

#: Query/fragment parameter names that carry a credential in our links (and in
#: the links of the apps that send through Janua). Lowercase; exact match.
TOKEN_PARAM_NAMES = frozenset(
    {
        "token",
        "access_token",
        "id_token",
        "refresh_token",
        "magic",
        "magic_token",
        "code",
        "otp",
        "sig",
        "signature",
        "jwt",
        "key",
        "secret",
        "nonce",
        "ticket",
        "invite",
        "invitation",
        "invite_token",
        "reset_token",
        "verification_token",
    }
)


def domain_of(address: Optional[str]) -> str:
    """Lowercased domain of an address (display-name forms tolerated), or ""."""
    if not address or "@" not in address:
        return ""
    return address.rsplit("@", 1)[1].strip().strip(">").lower()


def is_tracked_sender(address: Optional[str]) -> bool:
    """True when mail FROM `address` goes out on a domain with tracking enabled."""
    domain = domain_of(address)
    return bool(domain) and domain in settings.email_tracked_sender_domains_list


class _LinkAndTextParser(HTMLParser):
    """Collects hrefs and a readable plain-text rendering of an HTML body."""

    _SKIP = {"style", "script", "head", "title"}
    _BREAK = {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: List[str] = []
        self._chunks: List[str] = []
        self._skip_depth = 0
        self._href_stack: List[Optional[str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
            return
        if tag in self._BREAK:
            self._chunks.append("\n")
        if tag == "a":
            href = next((v for k, v in attrs if k == "href" and v), None)
            if href:
                self.hrefs.append(href.strip())
            self._href_stack.append(href.strip() if href else None)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "a" and self._href_stack:
            href = self._href_stack.pop()
            if href and not href.lower().startswith(("mailto:", "#")):
                self._chunks.append(f" {href} ")
        if tag in self._BREAK:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._chunks.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self._chunks).splitlines()]
        out: List[str] = []
        for line in lines:
            if line or (out and out[-1]):
                out.append(line)
        return "\n".join(out).strip()


def _parse(html: str) -> _LinkAndTextParser:
    parser = _LinkAndTextParser()
    parser.feed(html or "")
    parser.close()
    return parser


def url_carries_token(url: str) -> bool:
    """True when `url`'s query or fragment has a credential-looking parameter."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    for component in (parts.query, parts.fragment):
        for name, _value in parse_qsl(component, keep_blank_values=True):
            if name.strip().lower() in TOKEN_PARAM_NAMES:
                return True
    return False


def html_carries_token_link(html: Optional[str]) -> bool:
    """True when any link in the HTML body carries a credential parameter."""
    if not html:
        return False
    return any(url_carries_token(href) for href in _parse(html).hrefs)


def html_to_text(html: str) -> str:
    """A plain-text rendering of an HTML body, links written out in full."""
    return _parse(html).text()


def _present(body: Optional[str]) -> Optional[str]:
    """The body, or None when it is missing, empty or whitespace-only.

    An empty `"html": ""` handed to Resend is not "no HTML": it can arrive as
    a blank HTML part that mail clients prefer over the real text part, so a
    text-only message reads as an empty email. Every transport omits a body
    this returns None for.
    """
    return body if body is not None and body.strip() else None


def untracked_bodies(
    from_address: Optional[str],
    html: Optional[str],
    text: Optional[str],
    *,
    token_link: bool = False,
) -> Tuple[Optional[str], Optional[str], bool]:
    """(html, text, forced_text_only) to put on the wire for one message.

    Blank bodies come back as None (see `_present`), so a text-only message
    never carries an empty HTML part. Otherwise the bodies are unchanged unless
    the message is token-bearing AND its From domain is tracked; then the HTML
    is dropped and the text part is the caller's own, or one derived from the
    HTML so the link still arrives.
    """
    html, text = _present(html), _present(text)
    if not is_tracked_sender(from_address):
        return html, text, False
    if not (token_link or html_carries_token_link(html)):
        return html, text, False
    plain = text if text is not None else html_to_text(html or "")
    return None, _present(plain), True
