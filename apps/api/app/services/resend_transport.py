"""Serialize the SDK's process-global account across every Janua mail adapter."""

import threading
from datetime import datetime
from typing import Any

import resend

_ACCOUNT_LOCK = threading.Lock()


def send_on_account(
    params: dict[str, Any],
    api_key: str,
    *,
    idempotency_key: str | None = None,
    send_before: datetime | None = None,
) -> dict[str, Any]:
    """Use only the selected account and restore ambient SDK state on all paths."""
    if not api_key:
        raise ValueError("Email account credential is unavailable")
    with _ACCOUNT_LOCK:
        # Recheck after waiting for another adapter; a queued worker must never
        # send outside the provider deduplication window.
        if send_before is not None and datetime.utcnow() >= send_before:
            raise TimeoutError("Email idempotency window expired")
        previous_key = resend.api_key
        resend.api_key = api_key
        try:
            response = (
                resend.Emails.send(params, {"idempotency_key": idempotency_key})
                if idempotency_key is not None
                else resend.Emails.send(params)
            )
            if (
                not isinstance(response, dict)
                or not isinstance(response.get("id"), str)
                or not response["id"].strip()
            ):
                raise ValueError("Email provider returned no acceptance receipt")
            return response
        finally:
            resend.api_key = previous_key
