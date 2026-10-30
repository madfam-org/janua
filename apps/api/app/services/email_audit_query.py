"""Bounded, organization-scoped intent/verified-receipt reads; no message content."""

from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import String, and_, case, cast, func, or_, select, text

from app.models.email_dispatch import PaymentMailDispatch
from app.models.email_event import EmailEvent
from app.models.email_send_audit import EmailSendAudit


def utc(value):
    if value is None:
        return None
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def event_scope(org_id, source_app):
    return and_(
        EmailEvent.org_id == str(org_id),
        EmailEvent.source_app == source_app,
        EmailEvent.source == "webhook",
    )


def proof(model, org_id, source_app, kind):
    return (
        select(EmailEvent.id)
        .where(
            event_scope(org_id, source_app),
            EmailEvent.event_type == kind,
            or_(
                EmailEvent.mail_audit_id == cast(model.id, String),
                and_(
                    model.provider_message_id.is_not(None),
                    EmailEvent.email_id == model.provider_message_id,
                ),
            ),
        )
        .exists()
    )


def folio_match(model, folio):
    native = model is PaymentMailDispatch
    return or_(
        model.id == folio,
        model.map_audit_id == str(folio) if native else model.upstream_audit_id == folio,
        model.command_id == folio if native else False,
    )


async def provider_window(db, *, models, org_id, source_app, lower, upper, folio):
    matching, older = [], []
    for model, source_filters in models:
        conditions = list(source_filters)
        if folio is not None:
            conditions.append(folio_match(model, folio))
        conditions.append(
            or_(
                EmailEvent.mail_audit_id == cast(model.id, String),
                and_(
                    model.provider_message_id.is_not(None),
                    EmailEvent.email_id == model.provider_message_id,
                ),
            )
        )
        matching.append(select(model.id).where(*conditions).correlate(EmailEvent).exists())
        older.append(
            select(model.id)
            .where(*conditions, model.created_at < lower)
            .correlate(EmailEvent)
            .exists()
        )
    row = (
        (
            await db.execute(
                select(
                    func.count(
                        func.distinct(
                            case(
                                (EmailEvent.event_type == "email.sent", EmailEvent.email_id),
                                else_=None,
                            )
                        )
                    ).label("verified_sent"),
                    func.count(
                        func.distinct(
                            case(
                                (EmailEvent.event_type == "email.delivered", EmailEvent.email_id),
                                else_=None,
                            )
                        )
                    ).label("verified_delivered"),
                    func.count(case((or_(*older), EmailEvent.id), else_=None)).label(
                        "events_for_older_intents"
                    ),
                )
                .select_from(EmailEvent)
                .where(
                    event_scope(org_id, source_app),
                    EmailEvent.event_type.in_(["email.sent", "email.delivered"]),
                    EmailEvent.occurred_at >= lower,
                    EmailEvent.occurred_at < upper,
                    or_(*matching),
                )
            )
        )
        .mappings()
        .one()
    )
    return {
        name: int(row[name])
        for name in ["verified_sent", "verified_delivered", "events_for_older_intents"]
    }


async def audit_page(
    db,
    *,
    org_id: UUID,
    source_app: str,
    start: datetime,
    end: datetime,
    folio: UUID | None,
    limit: int,
):
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        await db.execute(text("SET TRANSACTION READ ONLY"))
        await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        await db.execute(text("SET LOCAL statement_timeout='5s'"))
    lower, upper = [value.astimezone(timezone.utc).replace(tzinfo=None) for value in (start, end)]
    models = [
        (
            EmailSendAudit,
            [EmailSendAudit.org_id == str(org_id), EmailSendAudit.source_app == source_app],
        )
    ]
    if source_app == "crea-map":
        models.append((PaymentMailDispatch, [PaymentMailDispatch.organization_id == org_id]))
    records, state_counts = [], Counter()
    totals = Counter(recorded_intents=0, provider_accepted=0, verified_sent=0, verified_delivered=0)
    for model, conditions in models:
        conditions = list(conditions)
        native = model is PaymentMailDispatch
        conditions += [model.created_at >= lower, model.created_at < upper]
        if folio is not None:
            conditions.append(folio_match(model, folio))
        stats = (
            (
                await db.execute(
                    select(
                        model.state.label("state"),
                        func.count().label("recorded_intents"),
                        func.sum(
                            case(
                                (
                                    and_(
                                        model.provider_message_id.is_not(None),
                                        model.accepted_at.is_not(None),
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ).label("provider_accepted"),
                        func.sum(
                            case((proof(model, org_id, source_app, "email.sent"), 1), else_=0)
                        ).label("verified_sent"),
                        func.sum(
                            case((proof(model, org_id, source_app, "email.delivered"), 1), else_=0)
                        ).label("verified_delivered"),
                    )
                    .where(*conditions)
                    .group_by(model.state)
                )
            )
            .mappings()
            .all()
        )
        for row in stats:
            state_counts[row["state"]] += row["recorded_intents"]
            for name in totals:
                totals[name] += int(row[name] or 0)
        columns = [
            model.id.label("audit_id"),
            model.state,
            model.provider_message_id,
            model.created_at.label("requested_at"),
            model.accepted_at.label("resolved_at"),
        ]
        if native:
            columns += [
                model.map_audit_id,
                model.command_id,
                model.first_attempt_at.label("attempted_at"),
            ]
        else:
            columns += [
                model.upstream_audit_id.label("map_audit_id"),
                model.provenance,
                model.message_kind,
                model.trigger_kind,
                model.attempted_at,
            ]
        rows = (
            (
                await db.execute(
                    select(*columns)
                    .where(*conditions)
                    .order_by(model.created_at.desc(), model.id.desc())
                    .limit(limit + 1)
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            item = dict(row)
            item.update(source_app=source_app)
            if native:
                item.update(
                    provenance="verified_mail_client",
                    message_kind="payment",
                    trigger_kind="payment_command",
                )
            else:
                item["command_id"] = None
            for key in ["audit_id", "map_audit_id", "command_id"]:
                item[key] = str(item[key]) if item[key] is not None else None
            for key in ["requested_at", "resolved_at", "attempted_at"]:
                item[key] = utc(item[key])
            item.update(verified_sent_at=None, verified_delivered_at=None)
            records.append(item)
    records.sort(key=lambda row: (row["requested_at"], row["audit_id"]), reverse=True)
    page = records[:limit]
    identities = [row["audit_id"] for row in page]
    providers = [row["provider_message_id"] for row in page if row["provider_message_id"]]
    if identities or providers:
        events = (
            (
                await db.execute(
                    select(
                        EmailEvent.mail_audit_id,
                        EmailEvent.email_id,
                        EmailEvent.event_type,
                        func.min(EmailEvent.occurred_at).label("occurred_at"),
                    )
                    .where(
                        event_scope(org_id, source_app),
                        EmailEvent.event_type.in_(["email.sent", "email.delivered"]),
                        or_(
                            EmailEvent.mail_audit_id.in_(identities),
                            EmailEvent.email_id.in_(providers),
                        ),
                    )
                    .group_by(EmailEvent.mail_audit_id, EmailEvent.email_id, EmailEvent.event_type)
                )
            )
            .mappings()
            .all()
        )
        for row in page:
            matching = [
                event
                for event in events
                if event["mail_audit_id"] == row["audit_id"]
                or (row["provider_message_id"] and event["email_id"] == row["provider_message_id"])
            ]
            for kind, field in [
                ("email.sent", "verified_sent_at"),
                ("email.delivered", "verified_delivered_at"),
            ]:
                row[field] = min(
                    (
                        utc(event["occurred_at"])
                        for event in matching
                        if event["event_type"] == kind
                    ),
                    default=None,
                )
            # A native payment response can be lost after provider acceptance.
            # Expose an exact provider ID only when the verified join is unique.
            if row["provider_message_id"] is None:
                known = {event["email_id"] for event in matching}
                if len(known) == 1:
                    row["provider_message_id"] = next(iter(known))
    events_in_window = await provider_window(
        db,
        models=models,
        org_id=org_id,
        source_app=source_app,
        lower=lower,
        upper=upper,
        folio=folio,
    )
    return {
        "records": page,
        "provider_events_in_window": events_in_window,
        "summary": {
            "total": totals["recorded_intents"],
            "provider_accepted": totals["provider_accepted"],
            "verified_sent": totals["verified_sent"],
            "verified_delivered": totals["verified_delivered"],
            "states": dict(state_counts),
        },
        "org_id": org_id,
        "source_app": source_app,
        "has_more": totals["recorded_intents"] > len(page),
        "coverage": "recorded_intents_only_no_backfill",
        "history_complete": False,
        "window_applies_to": "requested_at",
        "from": start,
        "to": end,
        "observed_through": datetime.now(timezone.utc),
    }
