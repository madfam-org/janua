"""Org-bound machine-only payment notices, independent of legacy internal keys."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.payment_mail_auth import PaymentMailPrincipal, payment_mail_principal
from app.services.payment_mail_dispatch import (
    PaymentNoticeIntent,
    PaymentNoticeReceipt,
    dispatch_payment_notice,
)

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/payment-notices", response_model=PaymentNoticeReceipt)
async def payment_notice(
    intent: PaymentNoticeIntent,
    principal: PaymentMailPrincipal = Depends(payment_mail_principal),
    db: AsyncSession = Depends(get_db),
):
    """Submit/replay a stable command; accepted is provider acceptance, not delivery."""
    return await dispatch_payment_notice(db, principal, intent)
