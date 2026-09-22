"""Serialize the SDK's process-global account across every Janua mail adapter."""

import threading
from typing import Any

import resend

_ACCOUNT_LOCK = threading.Lock()


def send_on_account(params: dict[str, Any], api_key: str) -> dict[str, Any]:
    """Use only the selected account and restore ambient SDK state on all paths."""
    if not api_key:
        raise ValueError("Email account credential is unavailable")
    with _ACCOUNT_LOCK:
        previous_key = resend.api_key
        resend.api_key = api_key
        try:
            response = resend.Emails.send(params)
            if (
                not isinstance(response, dict)
                or not isinstance(response.get("id"), str)
                or not response["id"].strip()
            ):
                raise ValueError("Email provider returned no acceptance receipt")
            return response
        finally:
            resend.api_key = previous_key
