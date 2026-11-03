"""Short-lived, browser-bound continuation state; never stores bearer tokens."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.redis_circuit_breaker import ResilientRedisClient

TRANSACTION_TTL = 120
CODE_TTL = 30
FINALIZATION_TTL = 30
_OPAQUE = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_PREFIX = "auth:session-bridge:v1:"


class InvalidBridgeState(ValueError):
    """Absent, expired, mismatched or already-consumed continuation state."""


def _hash(value: str) -> str:
    if not isinstance(value, str) or _OPAQUE.fullmatch(value) is None:
        raise InvalidBridgeState()
    return hashlib.sha256(value.encode()).hexdigest()


def _serialize(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, allow_nan=False)


def _parse(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, (str, bytes)):
        raise InvalidBridgeState()
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        raise InvalidBridgeState() from None
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value["version"] != 1
    ):
        raise InvalidBridgeState()
    expires = value.get("expires_at")
    if type(expires) is not int or expires <= time.time():
        raise InvalidBridgeState()
    return value


@dataclass(frozen=True)
class StartedBridge:
    state: str = field(repr=False)
    browser_secret: str = field(repr=False)


@dataclass(frozen=True)
class IssuedBridge:
    code: str = field(repr=False)
    expires_at: int


@dataclass(frozen=True)
class BoundBridge:
    transaction: dict[str, Any] = field(repr=False)
    proof: dict[str, Any] = field(repr=False)
    expected: dict[str, str | bytes] = field(repr=False)


@dataclass(frozen=True)
class ApprovedBridge:
    transaction: dict[str, Any] = field(repr=False)
    proof: dict[str, Any] = field(repr=False)
    expected: dict[str, str | bytes] = field(repr=False)
    expires_at: int


class BridgeStateStore:
    def __init__(self, redis: ResilientRedisClient):
        self.redis = redis

    async def start(
        self,
        *,
        source_client_id: str,
        source_uri: str,
        source_audience: str,
        target_client_id: str,
        authorization: dict[str, str],
    ) -> StartedBridge:
        """Caller has validated both clients and exact registered callback URIs."""
        state, browser_secret = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        value = {
            "version": 1,
            "source_client_id": source_client_id,
            "source_uri": source_uri,
            "source_audience": source_audience,
            "target_client_id": target_client_id,
            "authorization": authorization,
            "browser_hash": _hash(browser_secret),
            "expires_at": int(time.time()) + TRANSACTION_TTL,
        }
        await self.redis.strict_set(
            _PREFIX + "transaction:" + _hash(state),
            _serialize(value),
            ex=TRANSACTION_TTL,
        )
        return StartedBridge(state, browser_secret)

    async def read(self, state: str) -> tuple[str | bytes, dict[str, Any]]:
        raw = await self.redis.strict_get(_PREFIX + "transaction:" + _hash(state))
        return raw, _parse(raw)

    async def issue(self, state: str, proof: dict[str, Any]) -> IssuedBridge:
        """Caller supplies only previously validated session/revocation references."""
        _, transaction = await self.read(state)
        now = int(time.time())
        proof_expiry = proof.get("expires_at")
        if type(proof_expiry) is not int:
            raise InvalidBridgeState()
        expires = min(now + CODE_TTL, transaction["expires_at"], proof_expiry)
        if expires <= now:
            raise InvalidBridgeState()
        # Whitelist references: raw credentials can never become Redis payloads.
        fields = (
            "user_id",
            "session_id",
            "parent_family",
            "proof_jti",
            "proof_family",
            "proof_type",
            "source_client_id",
            "proof_kind",
            "assurance_hash",
        )
        if any(not isinstance(proof.get(key), str) or not proof[key] for key in fields):
            raise InvalidBridgeState()
        if proof["source_client_id"] != transaction["source_client_id"]:
            raise InvalidBridgeState()
        if proof["proof_type"] not in ("access", "refresh"):
            raise InvalidBridgeState()
        if (
            proof["proof_kind"] not in ("direct", "oidc")
            or re.fullmatch(r"[0-9a-f]{64}", proof["assurance_hash"]) is None
        ):
            raise InvalidBridgeState()
        if proof["proof_kind"] == "oidc" and proof["proof_type"] != "refresh":
            raise InvalidBridgeState()
        code = secrets.token_urlsafe(32)
        state_hash, code_hash = _hash(state), _hash(code)
        stored = {key: proof[key] for key in fields}
        stored.update(version=1, state_hash=state_hash, expires_at=expires)
        if not await self.redis.strict_set_nx(
            _PREFIX + "issued:" + state_hash,
            code_hash,
            ex=expires - now,
        ):
            raise InvalidBridgeState()
        if not await self.redis.strict_set_nx(
            _PREFIX + "code:" + code_hash,
            _serialize(stored),
            ex=expires - now,
        ):
            raise InvalidBridgeState()
        return IssuedBridge(code, expires)

    async def browser_transaction(self, state: str, browser_secret: str):
        raw, transaction = await self.read(state)
        browser_hash = transaction.get("browser_hash")
        if not isinstance(browser_hash, str) or not hmac.compare_digest(
            browser_hash, _hash(browser_secret)
        ):
            raise InvalidBridgeState()
        return raw, transaction

    async def cancel(self, state: str, browser_secret: str):
        """A bound browser may abandon its transaction, never establish a session."""
        raw, transaction = await self.browser_transaction(state, browser_secret)
        if not await self.redis.strict_compare_delete(
            {_PREFIX + "transaction:" + _hash(state): raw}
        ):
            raise InvalidBridgeState()
        return transaction

    async def bound(self, state: str, code: str, browser_secret: str) -> BoundBridge:
        state_hash, code_hash = _hash(state), _hash(code)
        transaction_raw, transaction = await self.browser_transaction(state, browser_secret)
        code_key = _PREFIX + "code:" + code_hash
        code_raw = await self.redis.strict_get(code_key)
        proof = _parse(code_raw)
        if proof.get("state_hash") != state_hash:
            raise InvalidBridgeState()
        if proof.get("source_client_id") != transaction.get("source_client_id"):
            raise InvalidBridgeState()
        issued_key = _PREFIX + "issued:" + state_hash
        issued_raw = await self.redis.strict_get(issued_key)
        if issued_raw not in (code_hash, code_hash.encode()):
            raise InvalidBridgeState()
        return BoundBridge(
            transaction,
            proof,
            {
                _PREFIX + "transaction:" + state_hash: transaction_raw,
                code_key: code_raw,
                issued_key: issued_raw,
            },
        )

    async def consume(self, bound: BoundBridge) -> None:
        """Run only after rechecking live identity, session and client authority."""
        if min(bound.transaction["expires_at"], bound.proof["expires_at"]) <= time.time():
            raise InvalidBridgeState()
        if not await self.redis.strict_compare_delete(bound.expected):
            raise InvalidBridgeState()

    async def approve(self, bound: BoundBridge) -> IssuedBridge:
        """Burn the source tuple before staging proof refs for a private-cookie GET.

        A failed staging write loses this attempt, never restores the consumed
        source grant or creates an in-process fallback.
        """
        now = int(time.time())
        expires = min(
            now + FINALIZATION_TTL, bound.transaction["expires_at"], bound.proof["expires_at"]
        )
        if expires <= now:
            raise InvalidBridgeState()
        secret = secrets.token_urlsafe(32)
        value = {
            "version": 1,
            "phase": "finalization",
            "expires_at": expires,
            "transaction": bound.transaction,
            "proof": bound.proof,
        }
        await self.consume(bound)
        if not await self.redis.strict_set_nx(
            _PREFIX + "approved:" + _hash(secret), _serialize(value), ex=expires - now
        ):
            raise InvalidBridgeState()
        return IssuedBridge(secret, expires)

    async def approved(self, secret: str) -> ApprovedBridge:
        key = _PREFIX + "approved:" + _hash(secret)
        raw = await self.redis.strict_get(key)
        value = _parse(raw)
        transaction, proof = value.get("transaction"), value.get("proof")
        if (
            value.get("phase") != "finalization"
            or not isinstance(transaction, dict)
            or not isinstance(proof, dict)
            or type(transaction.get("expires_at")) is not int
            or type(proof.get("expires_at")) is not int
            or value["expires_at"] > min(transaction["expires_at"], proof["expires_at"])
        ):
            raise InvalidBridgeState()
        return ApprovedBridge(transaction, proof, {key: raw}, value["expires_at"])

    async def consume_approval(self, approved: ApprovedBridge) -> None:
        if approved.expires_at <= time.time():
            raise InvalidBridgeState()
        if not await self.redis.strict_compare_delete(approved.expected):
            raise InvalidBridgeState()
