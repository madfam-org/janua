#!/usr/bin/env python3
"""Rotation monitor — alert when SECRETS_REGISTRY.yaml entries are overdue.

Runs daily via k8s CronJob. Parses ``infra/secrets/SECRETS_REGISTRY.yaml``,
computes each secret's days-past-due, and emits a structured alert
(stdout + optional Slack webhook) when any secret has:

  - crossed its ``next_rotation`` date, OR
  - entered the reminder window (``policy.reminder_days`` before due).

Exit codes:
  0  — everything within reminder window, nothing overdue, nothing alerted
  1  — at least one secret overdue OR reminder fired (Alertmanager scrapes
       K8s Job exit codes; 1 pages on-call)
  2  — registry parse / IO error (paging condition)

Zero external dependencies beyond pyyaml + urllib (stdlib). This is
deliberate — the monitor must run in the smallest possible image so its
own rotation story is trivial.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

# Default reminder windows per policy — matches the YAML's rotation_policies.
# If a policy is missing reminder_days we fall back to this table so the
# monitor still fires a week before due.
DEFAULT_REMINDERS = {
    "quarterly": [14, 7, 3, 1],
    "semi_annual": [30, 14, 7, 3, 1],
    "annual": [30, 14, 7, 1],
    "on_demand": [],
}

BOOTSTRAP_SENTINEL = "BOOTSTRAP_REQUIRED"


@dataclass(frozen=True)
class Finding:
    """One entry's evaluation result."""

    project: str
    secret_id: str
    name: str
    policy: str
    next_rotation: str | None
    days_past_due: int  # negative = still within window; positive = overdue
    severity: str  # "overdue" | "reminder" | "ok" | "bootstrap" | "skipped"
    reason: str

    @property
    def is_actionable(self) -> bool:
        """Return True when this finding should raise the exit code."""
        return self.severity in ("overdue", "bootstrap", "reminder")


def _today() -> date:
    """Factored out so tests can override ``today`` deterministically."""
    return datetime.now(timezone.utc).date()


def _parse_date(value: str | None) -> date | None:
    if not value or value in (BOOTSTRAP_SENTINEL, "unknown", "null"):
        return None
    try:
        return date.fromisoformat(value.split(" ")[0])
    except ValueError:
        return None


def _classify(
    secret: dict[str, Any],
    project: str,
    policies: dict[str, dict[str, Any]],
    today: date,
) -> Finding:
    secret_id = secret.get("id", "<unknown>")
    name = secret.get("name", "")
    policy_name = secret.get("policy", "unknown")
    raw_last = secret.get("last_rotated")
    raw_next = secret.get("next_rotation")

    # Bootstrap case — operator has never set a real rotation baseline.
    # Treat as actionable so the cohort doesn't drift silently.
    if raw_last == BOOTSTRAP_SENTINEL:
        # Respect an explicit next_rotation date even during bootstrap
        # so we don't alert immediately for every bootstrap entry.
        next_d = _parse_date(raw_next)
        if next_d and next_d > today:
            return Finding(
                project=project,
                secret_id=secret_id,
                name=name,
                policy=policy_name,
                next_rotation=raw_next,
                days_past_due=(today - next_d).days,
                severity="bootstrap",
                reason=(
                    f"first rotation not yet performed — "
                    f"bootstrap baseline due {raw_next} "
                    f"(in {(next_d - today).days} days)"
                ),
            )
        return Finding(
            project=project,
            secret_id=secret_id,
            name=name,
            policy=policy_name,
            next_rotation=raw_next,
            days_past_due=0 if not next_d else (today - next_d).days,
            severity="bootstrap",
            reason="first rotation not yet performed — operator must set baseline",
        )

    next_d = _parse_date(raw_next)
    if next_d is None:
        if policy_name == "on_demand":
            return Finding(
                project=project,
                secret_id=secret_id,
                name=name,
                policy=policy_name,
                next_rotation=raw_next,
                days_past_due=0,
                severity="skipped",
                reason="on_demand policy — no scheduled rotation",
            )
        return Finding(
            project=project,
            secret_id=secret_id,
            name=name,
            policy=policy_name,
            next_rotation=raw_next,
            days_past_due=0,
            severity="skipped",
            reason=f"next_rotation missing or unparseable: {raw_next!r}",
        )

    days_past = (today - next_d).days

    if days_past >= 0:
        return Finding(
            project=project,
            secret_id=secret_id,
            name=name,
            policy=policy_name,
            next_rotation=raw_next,
            days_past_due=days_past,
            severity="overdue",
            reason=f"rotation {days_past} days past due (was {raw_next})",
        )

    days_until = -days_past
    reminders = (
        policies.get(policy_name, {}).get("reminder_days")
        or DEFAULT_REMINDERS.get(policy_name, [])
    )
    if reminders and days_until in set(reminders):
        return Finding(
            project=project,
            secret_id=secret_id,
            name=name,
            policy=policy_name,
            next_rotation=raw_next,
            days_past_due=-days_until,
            severity="reminder",
            reason=f"rotation due in {days_until} days (reminder window)",
        )

    return Finding(
        project=project,
        secret_id=secret_id,
        name=name,
        policy=policy_name,
        next_rotation=raw_next,
        days_past_due=-days_until,
        severity="ok",
        reason=f"within policy — {days_until} days until rotation",
    )


def load_registry(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError("registry root must be a mapping")
    return data


def iter_secrets(
    registry: dict[str, Any],
) -> Iterable[tuple[str, dict[str, Any]]]:
    secrets = registry.get("secrets", {})
    if not isinstance(secrets, dict):
        return
    for project, entries in secrets.items():
        if not isinstance(entries, list):
            continue
        for s in entries:
            if isinstance(s, dict):
                yield project, s


def evaluate(registry: dict[str, Any], today: date | None = None) -> list[Finding]:
    today = today or _today()
    policies = registry.get("rotation_policies") or {}
    return [
        _classify(secret, project, policies, today)
        for project, secret in iter_secrets(registry)
    ]


# -- Rendering / alerting -----------------------------------------------------


def _format_finding_line(f: Finding) -> str:
    tag = {
        "overdue": "❌ OVERDUE",
        "reminder": "⚠️  REMINDER",
        "bootstrap": "🌱 BOOTSTRAP",
        "ok": "✅ OK",
        "skipped": "⏭️  SKIP",
    }.get(f.severity, f.severity)
    return (
        f"{tag:<16} {f.project}/{f.secret_id} "
        f"[{f.policy}] · {f.reason}"
    )


def render_text_report(findings: list[Finding], today: date) -> str:
    actionable = [f for f in findings if f.is_actionable]
    lines = [
        "MADFAM Secrets Rotation Monitor",
        f"Run date: {today.isoformat()}",
        f"Total secrets tracked: {len(findings)}",
        f"Actionable: {len(actionable)} "
        f"(overdue={sum(1 for f in findings if f.severity == 'overdue')}, "
        f"reminder={sum(1 for f in findings if f.severity == 'reminder')}, "
        f"bootstrap={sum(1 for f in findings if f.severity == 'bootstrap')})",
        "",
    ]
    if actionable:
        lines.append("Actionable findings:")
        # Sort by severity priority then by days_past_due desc.
        priority = {"overdue": 0, "bootstrap": 1, "reminder": 2}
        for f in sorted(
            actionable, key=lambda f: (priority.get(f.severity, 9), -f.days_past_due)
        ):
            lines.append(f"  {_format_finding_line(f)}")
        lines.append("")
    return "\n".join(lines)


def _slack_payload(findings: list[Finding], today: date) -> dict[str, Any]:
    """Minimal Slack Incoming-Webhook payload. No SDK dep."""
    actionable = [f for f in findings if f.is_actionable]
    overdue = [f for f in actionable if f.severity == "overdue"]
    header = (
        f"🔐 Secrets rotation monitor — {today.isoformat()} · "
        f"{len(overdue)} overdue, {len(actionable)} total actionable"
    )
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": header}},
    ]
    for f in actionable[:20]:  # Slack message block limit
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{f.project}/{f.secret_id}* `{f.policy}` — "
                        f"{f.reason}"
                    ),
                },
            }
        )
    if len(actionable) > 20:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"...plus {len(actionable) - 20} more — see K8s Job log",
                    }
                ],
            }
        )
    return {"blocks": blocks}


def post_to_slack(webhook_url: str, payload: dict[str, Any]) -> bool:
    """Best-effort POST. Returns True on HTTP 2xx."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            return 200 <= resp.status < 300
    except urllib.error.URLError as exc:
        print(f"WARN: slack webhook failed: {exc}", file=sys.stderr)
        return False


# -- Entry point --------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rotation-monitor")
    p.add_argument(
        "--registry",
        default=os.environ.get(
            "SECRETS_REGISTRY_PATH",
            str(Path(__file__).resolve().parents[2] / "infra" / "secrets" / "SECRETS_REGISTRY.yaml"),
        ),
        help="Path to SECRETS_REGISTRY.yaml",
    )
    p.add_argument(
        "--slack-webhook-url",
        default=os.environ.get("SLACK_WEBHOOK_URL", ""),
        help="Slack incoming-webhook URL for actionable alerts. Optional.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit raw JSON findings on stdout instead of markdown.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    registry_path = Path(args.registry)

    try:
        registry = load_registry(registry_path)
    except (FileNotFoundError, yaml.YAMLError, ValueError) as exc:
        print(
            f"FATAL: could not load registry {registry_path}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    today = _today()
    findings = evaluate(registry, today=today)

    if args.json:
        sys.stdout.write(
            json.dumps(
                {
                    "as_of": today.isoformat(),
                    "findings": [f.__dict__ for f in findings],
                },
                indent=2,
            )
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_text_report(findings, today))

    actionable = [f for f in findings if f.is_actionable]
    if actionable and args.slack_webhook_url:
        post_to_slack(args.slack_webhook_url, _slack_payload(findings, today))

    return 1 if actionable else 0


if __name__ == "__main__":
    raise SystemExit(main())
