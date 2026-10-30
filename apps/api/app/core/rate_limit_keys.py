"""Who a per-IP rate limit counts: the client, not the hop in front of Janua.

Every slowapi limiter in the API used `slowapi.util.get_remote_address`, which
is `request.client.host`: the socket peer. Public traffic reaches the pods
through the tunnel, so that peer is a tunnel pod and every person behind it
shares one bucket per endpoint.

`client_ip_key` resolves the address the same way the sign-in link limits do
(`app.auth.magic_link_limits.trusted_client_ip`): forwarded headers count only
when the direct peer is in `TRUSTED_PROXIES` (exact addresses or CIDRs), so a
caller that is not a trusted proxy cannot pick its own bucket by sending
`X-Forwarded-For` or `CF-Connecting-IP`. IPv6 clients are counted per /64,
which one subscriber can rotate within.

The resolved address is only as good as `TRUSTED_PROXIES`: while the tunnel's
addresses are not listed there, the answer is still the tunnel pod.
"""

from __future__ import annotations

from starlette.requests import Request

from app.auth.magic_link_limits import _ip_bucket_key, trusted_client_ip


def client_ip_key(request: Request) -> str:
    """slowapi `key_func`: the trusted client address (IPv6 per /64)."""
    return _ip_bucket_key(trusted_client_ip(request))
