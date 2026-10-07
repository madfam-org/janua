"""HOW MANY SIGN-IN LINKS, FOR WHOM (2026-10-07).

## The defect this replaces

`POST /magic-link` and `POST /login-form/magic-link` were limited by slowapi at
`MAGIC_LINK_RATE_LIMIT` (5/hour) keyed on `request.client.host`. Two facts made
that key meaningless in production:

  * Uvicorn trusts forwarded headers only from 127.0.0.1, and every public
    request reaches the pod through the tunnel. So `client.host` is the tunnel
    pod's address for EVERYONE: one bucket for all public traffic, per pod.
  * Products ask for links from their SERVERS. Every person signing in to the
    MAP arrives as the MAP's one server.

So 5 links per hour served everyone, and the 6th person got a 429. The MAP
read that as success and told them «Revisa tu correo», and no email ever came.

## What limits what now

  * **Per address** (`MAGIC_LINK_EMAIL_RATE_LIMIT`, 5/hour). This is the
    email-bombing guard, and it applies to every caller. The key is a hash of
    the normalised address and is checked BEFORE any user lookup, so a 429 says
    nothing about whether an account exists.
  * **Per caller**, a ceiling far above any one person:
      - A trusted service (`X-Internal-API-Key` valid) gets its own bucket
        (`MAGIC_LINK_SERVICE_RATE_LIMIT`). Janua has one internal key today, so
        that is one "internal" bucket; the key itself is never hashed or stored.
        A service MAY also pass `X-Janua-End-User-IP`, the address of the
        person at ITS front door. It is believed only with a valid key, and
        gets the per-IP ceiling, so a public sign-in page behind a service
        keeps a per-visitor limit.
      - Anyone else gets the per-IP ceiling (`MAGIC_LINK_RATE_LIMIT`) on the
        address `trusted_client_ip` resolves. Forwarded headers count only when
        the direct peer is in `TRUSTED_PROXIES` (exact addresses or CIDRs).
        Until the tunnel's range is listed there, that peer is the tunnel, so
        this ceiling is shared by all anonymous traffic.

Counters are fixed windows in Redis, so every replica shares them. If Redis
does not answer, they fall back to this process's memory: protection
degrades, it does not disappear.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import structlog
from fastapi import HTTPException, Request
from limits import parse

from app.config import settings

logger = structlog.get_logger()

Address = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
Network = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]

#: The header a trusted service uses to name the person at its own front door.
END_USER_IP_HEADER = "X-Janua-End-User-IP"

#: What a rate-limited caller reads. Deliberately the same for every bucket:
#: which ceiling was hit is not the caller's business.
TOO_MANY_LINKS_DETAIL = "Too many sign-in links were requested. Wait a few minutes and try again."


@dataclass(frozen=True)
class Bucket:
    """One counter a request is charged against."""

    kind: str  # "email" | "service" | "ip" (logged; never the key itself)
    key: str
    amount: int
    seconds: int


def parse_limit(value: str) -> Tuple[int, int]:
    """`"5/hour"` -> `(5, 3600)`. Same grammar as slowapi (the `limits` package)."""
    item = parse(value)
    return int(item.amount), int(item.get_expiry())


def normalized_email(email: str) -> str:
    return (email or "").strip().lower()


def _address_digest(email: str) -> str:
    """The counter key for an address: a digest, never the address itself."""
    return hashlib.sha256(normalized_email(email).encode()).hexdigest()[:32]


def _trusted_networks() -> List[Network]:
    networks = []
    for raw in (settings.TRUSTED_PROXIES or "").split(","):
        entry = raw.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            continue
    return networks


def _parse_ip(value: Optional[str]) -> Optional[Address]:
    if not value:
        return None
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _is_trusted_proxy(address: Address, networks: List[Network]) -> bool:
    return any(address in network for network in networks)


def trusted_client_ip(request: Request) -> str:
    """The client's address, believing forwarded headers only from trusted proxies.

    If the direct peer is not in `TRUSTED_PROXIES`, its own address is the
    answer, whatever headers it sent. If it is trusted:
      1. `CF-Connecting-IP`, which Cloudflare sets and overwrites;
      2. else the RIGHT-most `X-Forwarded-For` entry that is not itself a
         trusted proxy. Left-most entries are whatever the client typed.
    """
    direct = request.client.host if request.client else ""
    direct_ip = _parse_ip(direct)
    networks = _trusted_networks()
    if direct_ip is None or not _is_trusted_proxy(direct_ip, networks):
        return direct or "unknown"

    connecting = _parse_ip(request.headers.get("cf-connecting-ip"))
    if connecting is not None:
        return str(connecting)

    forwarded = request.headers.get("x-forwarded-for") or ""
    for hop in reversed([h.strip() for h in forwarded.split(",") if h.strip()]):
        hop_ip = _parse_ip(hop)
        if hop_ip is None:
            break
        if not _is_trusted_proxy(hop_ip, networks):
            return str(hop_ip)
    return direct


def _ip_bucket_key(address: str) -> str:
    """IPv4 per address; IPv6 per /64, which one subscriber can rotate within."""
    parsed = _parse_ip(address)
    if isinstance(parsed, ipaddress.IPv6Address):
        return str(ipaddress.ip_network(f"{parsed}/64", strict=False))
    return str(parsed) if parsed is not None else address


def service_caller(request: Request) -> Optional[str]:
    """The service's bucket name when `X-Internal-API-Key` is VALID, else None.

    Janua has one internal key today, so every trusted service shares the
    "internal" bucket. The key itself never reaches a counter key, not even
    hashed. A wrong key is not an error here (this endpoint is public): the
    request is simply treated as anonymous, and the mismatch is logged so a
    misconfigured product is visible.
    """
    presented = request.headers.get("x-internal-api-key")
    if not presented:
        return None
    expected = settings.INTERNAL_API_KEY
    if expected and hmac.compare_digest(presented.encode(), expected.encode()):
        return "internal"
    logger.warning("magic_link.service_key_rejected")
    return None


def buckets_for(request: Request, email: str) -> List[Bucket]:
    """Every counter this request is charged against."""
    amount, seconds = parse_limit(settings.MAGIC_LINK_EMAIL_RATE_LIMIT)
    buckets = [Bucket("email", f"magic_link:rl:email:{_address_digest(email)}", amount, seconds)]
    ip_amount, ip_seconds = parse_limit(settings.MAGIC_LINK_RATE_LIMIT)
    service = service_caller(request)
    if service is not None:
        s_amount, s_seconds = parse_limit(settings.MAGIC_LINK_SERVICE_RATE_LIMIT)
        buckets.append(Bucket("service", f"magic_link:rl:service:{service}", s_amount, s_seconds))
        end_user = _parse_ip(request.headers.get(END_USER_IP_HEADER.lower()))
        if end_user is not None:
            key = _ip_bucket_key(str(end_user))
            buckets.append(Bucket("ip", f"magic_link:rl:ip:{key}", ip_amount, ip_seconds))
    else:
        key = _ip_bucket_key(trusted_client_ip(request))
        buckets.append(Bucket("ip", f"magic_link:rl:ip:{key}", ip_amount, ip_seconds))
    return buckets


# ---------------------------------------------------------------------------
# Counters: Redis first, this process's memory when Redis does not answer.
# ---------------------------------------------------------------------------

_memory: Dict[str, Tuple[int, float]] = {}


def reset_memory_counters() -> None:
    """Forget every in-process counter (tests; never called by the app)."""
    _memory.clear()


def _hit_memory(key: str, seconds: int) -> Tuple[int, int]:
    # No await between the read and the write: atomic under asyncio.
    now = time.monotonic()
    count, reset_at = _memory.get(key, (0, now + seconds))
    if reset_at <= now:
        count, reset_at = 0, now + seconds
    count += 1
    _memory[key] = (count, reset_at)
    if len(_memory) > 50_000:
        for stale in [k for k, (_, at) in _memory.items() if at <= now]:
            _memory.pop(stale, None)
    return count, max(1, int(reset_at - now))


async def _redis_client():
    from app.core.redis import get_raw_redis

    return await get_raw_redis()


async def _hit(bucket: Bucket) -> Tuple[int, int]:
    """Charge one request; returns (count in this window, seconds until it resets)."""
    try:
        client = await _redis_client()
        if client is not None:
            count = int(await client.incr(bucket.key))
            if count == 1:
                await client.expire(bucket.key, bucket.seconds)
                return count, bucket.seconds
            ttl = int(await client.ttl(bucket.key))
            if ttl < 0:  # a window that lost its expiry must not live forever
                await client.expire(bucket.key, bucket.seconds)
                ttl = bucket.seconds
            return count, ttl
    except Exception as exc:
        logger.warning("magic_link.limit_store_unavailable", error_type=type(exc).__name__)
    return _hit_memory(bucket.key, bucket.seconds)


async def enforce_magic_link_limits(request: Request, email: str) -> None:
    """Charge this request to its buckets; raise 429 when any is over its ceiling.

    Called before the user lookup and before anything is written, so the
    answer depends only on request counts, never on whether the account
    exists.
    """
    retry_after = 0
    over: List[str] = []
    for bucket in buckets_for(request, email):
        count, reset_in = await _hit(bucket)
        if count > bucket.amount:
            over.append(bucket.kind)
            retry_after = max(retry_after, reset_in)
    if over:
        logger.warning("magic_link.rate_limited", buckets=over, retry_after=retry_after)
        raise HTTPException(
            status_code=429,
            detail=TOO_MANY_LINKS_DETAIL,
            headers={"Retry-After": str(retry_after)},
        )
