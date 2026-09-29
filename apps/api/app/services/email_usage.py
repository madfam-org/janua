"""How much of a tenant's OWN Resend account quota has been used.

WHY. Crea Tu Mundo sends on its own Resend account (sender_binding.CTM_BINDING,
`account=tenant`), and that account is on a plan with a DAILY quota (100 on the
free plan) and a MONTHLY one (3,000). Everything that leaves the account counts:
the MAP's notices and billing mail, the sign-in links Janua sends for CTM hosts,
and whatever any other app sends as CTM. Janua is the only sender on that key, so
it is the one place that can answer "how many have we used today?" for all of
them at once. crea-map shows the meter and plans bulk sends around it.

THE SOURCE. Resend reports every accepted message to the account's webhook as
`email.sent`, and `email_events` already stores those per account (`cuenta`, the
same slug the webhook URL carries). Counting `email.sent` rows is therefore
counting what the provider accepted, whichever app sent it. Nothing new is
stored and nothing is written.

THE WINDOW is Resend's: the daily quota is the UTC calendar day (00:00-24:00 UTC,
reset at midnight UTC, not a rolling 24 h); the monthly one is taken as the UTC
calendar month (Resend does not document the monthly boundary more precisely).
`occurred_at` is naive UTC, the repo's convention.

LIMITS OF THE COUNT, stated so a caller can say them:
- a message with several To/CC/BCC recipients is ONE `email.sent` event but
  counts once PER RECIPIENT against the quota (Janua's internal send is one
  recipient per call, so this only matters for callers that pass cc/bcc);
- inbound mail also counts against Resend's quota and is not seen here;
- events arrive over the webhook a few seconds after the send.

The ACCOUNT an org resolves to is its sender binding's, and only a binding on
the tenant's OWN account is answered: the platform account is shared by every
tenant, and its usage is not one tenant's business.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_event import EmailEvent
from app.services.email_events import WEBHOOK_SECRET_SETTINGS, secret_for
from app.services.sender_binding import resolve_binding, tenant_for_org_id

#: The provider event that means "accepted for delivery": one per message.
SENT_EVENT = "email.sent"

#: Resend's quota error types (HTTP 429). `rate_limit_exceeded` is NOT a quota:
#: it is the per-second request limit and clears within a second.
QUOTA_ERROR_TYPES = frozenset({"daily_quota_exceeded", "monthly_quota_exceeded"})

MAX_DAYS = 31


def quota_error_code(exc: BaseException) -> Optional[str]:
    """`daily_quota_exceeded` / `monthly_quota_exceeded` when the provider
    refused for quota, else None.

    The resend SDK raises `RateLimitError` for all three 429 types and keeps the
    provider's type on `error_type`; reading the attribute (not the class) keeps
    this working across SDK versions and in tests without the SDK.
    """
    error_type = getattr(exc, "error_type", None)
    return error_type if isinstance(error_type, str) and error_type in QUOTA_ERROR_TYPES else None


def account_for_org(org_id: Optional[str]) -> Optional[str]:
    """The Resend account slug (`cuenta`) an org sends on, if it is the org's own.

    None when the org has no binding, when its binding sends on MADFAM's shared
    account, or when the account has no webhook slug (no events to count).
    """
    tenant = tenant_for_org_id(org_id)
    if tenant is None:
        return None
    binding = resolve_binding(tenant)
    if not binding.is_on_tenant_account:
        return None
    return tenant if tenant in WEBHOOK_SECRET_SETTINGS else None


def webhook_configured(cuenta: str) -> bool:
    """Whether events for the account can be arriving at all."""
    return secret_for(cuenta) is not None


def _day_start(moment: datetime) -> datetime:
    return datetime(moment.year, moment.month, moment.day)


@dataclass(frozen=True)
class Usage:
    cuenta: str
    as_of: datetime
    today: int
    month: int
    days: List[Dict[str, Any]]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "cuenta": self.cuenta,
            "window": "utc_day",
            "as_of": self.as_of,
            "today": self.today,
            "month": self.month,
            "days": self.days,
        }


async def usage_for_account(
    db: AsyncSession, cuenta: str, days: int, now: Optional[datetime] = None
) -> Usage:
    """Accepted messages on one account: today, this month, and the last `days` days.

    `days` includes today and is ordered oldest first; a day with no sends is 0.
    One read of the send timestamps from the earlier of the month
    start and the first day asked for, bucketed here (portable across the
    PostgreSQL of production and the SQLite of the unit tests).
    """
    days = max(1, min(days, MAX_DAYS))
    current = now or datetime.utcnow()
    today_start = _day_start(current)
    month_start = datetime(current.year, current.month, 1)
    first_day = today_start - timedelta(days=days - 1)
    since = min(month_start, first_day)

    result = await db.execute(
        select(EmailEvent.occurred_at).where(
            EmailEvent.cuenta == cuenta,
            EmailEvent.event_type == SENT_EVENT,
            EmailEvent.occurred_at >= since,
        )
    )
    per_day: Dict[date, int] = {}
    month = 0
    for (occurred_at,) in result.all():
        if occurred_at is None:
            continue
        per_day[occurred_at.date()] = per_day.get(occurred_at.date(), 0) + 1
        if occurred_at >= month_start:
            month += 1

    series = [
        {
            "date": (first_day + timedelta(days=i)).date().isoformat(),
            "sent": per_day.get((first_day + timedelta(days=i)).date(), 0),
        }
        for i in range(days)
    ]
    return Usage(
        cuenta=cuenta,
        as_of=current,
        today=per_day.get(today_start.date(), 0),
        month=month,
        days=series,
    )
