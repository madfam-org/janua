#!/usr/bin/env python3
"""
MADFAM Secrets Rotation Schedule Checker

Parses SECRETS_REGISTRY.yaml and checks rotation schedule.
Outputs:
- Overdue secrets requiring immediate attention
- Upcoming rotations within reminder windows
- Status report for monitoring integration

Exit codes:
- 0: No overdue secrets
- 1: Has overdue secrets (CRITICAL)
- 2: Configuration/parse error

Usage:
  python check-rotation-schedule.py
  python check-rotation-schedule.py --output json
  python check-rotation-schedule.py --slack-format
  python check-rotation-schedule.py --github-format
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


@dataclass
class SecretStatus:
    """Status of a single secret's rotation schedule."""
    id: str
    name: str
    project: str
    location: str
    policy: str
    last_rotated: Optional[date]
    next_rotation: Optional[date]
    days_until: Optional[int]
    owner: str
    risk_level: str
    procedure: str
    status: str  # 'overdue', 'due_soon', 'upcoming', 'ok', 'on_demand'
    dependencies: list


def find_registry_path() -> Path:
    """Locate SECRETS_REGISTRY.yaml relative to script or cwd."""
    candidates = [
        Path(__file__).parent.parent.parent / "infra" / "secrets" / "SECRETS_REGISTRY.yaml",
        Path.cwd() / "infra" / "secrets" / "SECRETS_REGISTRY.yaml",
        Path.cwd() / "SECRETS_REGISTRY.yaml",
    ]

    # Check environment variable override
    env_path = os.environ.get("SECRETS_REGISTRY_PATH")
    if env_path:
        candidates.insert(0, Path(env_path))

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        f"SECRETS_REGISTRY.yaml not found. Searched: {[str(p) for p in candidates]}"
    )


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse ISO date string to date object."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).date()
    except (ValueError, TypeError):
        return None


def check_secret_status(secret: dict, project: str, today: date) -> SecretStatus:
    """Determine the rotation status of a single secret."""
    next_rot = parse_date(secret.get("next_rotation"))
    last_rot = parse_date(secret.get("last_rotated"))
    policy = secret.get("policy", "unknown")

    # Handle on_demand secrets
    if policy == "on_demand" or next_rot is None:
        days_until = None
        status = "on_demand"
    else:
        days_until = (next_rot - today).days
        if days_until < 0:
            status = "overdue"
        elif days_until <= 3:
            status = "due_soon"
        elif days_until <= 14:
            status = "upcoming"
        else:
            status = "ok"

    return SecretStatus(
        id=secret.get("id", "unknown"),
        name=secret.get("name", "unknown"),
        project=project,
        location=secret.get("location", "unknown"),
        policy=policy,
        last_rotated=last_rot,
        next_rotation=next_rot,
        days_until=days_until,
        owner=secret.get("owner", "unknown"),
        risk_level=secret.get("risk_level", "unknown"),
        procedure=secret.get("procedure", "manual"),
        status=status,
        dependencies=secret.get("dependencies", [])
    )


def check_rotations(registry_path: Path) -> tuple[list[SecretStatus], list[SecretStatus], list[SecretStatus]]:
    """
    Parse registry and categorize secrets by rotation status.

    Returns:
        Tuple of (overdue, due_soon, upcoming) secret lists
    """
    with open(registry_path) as f:
        registry = yaml.safe_load(f)

    today = date.today()
    overdue = []
    due_soon = []
    upcoming = []

    secrets_data = registry.get("secrets", {})

    for project, project_secrets in secrets_data.items():
        if not isinstance(project_secrets, list):
            continue

        for secret in project_secrets:
            status = check_secret_status(secret, project, today)

            if status.status == "overdue":
                overdue.append(status)
            elif status.status == "due_soon":
                due_soon.append(status)
            elif status.status == "upcoming":
                upcoming.append(status)

    # Sort by urgency (most overdue first, then by days until)
    overdue.sort(key=lambda s: s.days_until if s.days_until else 0)
    due_soon.sort(key=lambda s: s.days_until if s.days_until else 999)
    upcoming.sort(key=lambda s: s.days_until if s.days_until else 999)

    return overdue, due_soon, upcoming


def format_text_report(overdue: list, due_soon: list, upcoming: list) -> str:
    """Format a human-readable text report."""
    lines = []
    today = date.today().isoformat()

    lines.append("=" * 70)
    lines.append(f"MADFAM SECRETS ROTATION STATUS REPORT - {today}")
    lines.append("=" * 70)
    lines.append("")

    # Overdue (CRITICAL)
    if overdue:
        lines.append("🚨 OVERDUE SECRETS (IMMEDIATE ACTION REQUIRED)")
        lines.append("-" * 50)
        for s in overdue:
            lines.append(f"  [{s.project}] {s.id}")
            lines.append(f"     Name: {s.name}")
            lines.append(f"     Days overdue: {abs(s.days_until)}")
            lines.append(f"     Last rotated: {s.last_rotated}")
            lines.append(f"     Owner: {s.owner}")
            lines.append(f"     Risk level: {s.risk_level}")
            lines.append(f"     Procedure: {s.procedure}")
            lines.append("")
    else:
        lines.append("✅ No overdue secrets")
        lines.append("")

    # Due soon (WARNING)
    if due_soon:
        lines.append("⚠️  DUE WITHIN 3 DAYS")
        lines.append("-" * 50)
        for s in due_soon:
            lines.append(f"  [{s.project}] {s.id}")
            lines.append(f"     Due in: {s.days_until} days ({s.next_rotation})")
            lines.append(f"     Owner: {s.owner}")
            lines.append("")

    # Upcoming (INFO)
    if upcoming:
        lines.append("📅 UPCOMING (WITHIN 14 DAYS)")
        lines.append("-" * 50)
        for s in upcoming:
            lines.append(f"  [{s.project}] {s.id} - {s.days_until} days ({s.next_rotation})")

    lines.append("")
    lines.append("=" * 70)
    lines.append(f"Summary: {len(overdue)} overdue, {len(due_soon)} due soon, {len(upcoming)} upcoming")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_json_output(overdue: list, due_soon: list, upcoming: list) -> str:
    """Format JSON output for programmatic consumption."""
    # Security note: secret_to_dict outputs SECRET ROTATION METADATA only
    # (id, name, owner, rotation dates, policy) - NOT actual secret values/credentials.
    # This is intentional for rotation schedule monitoring and is safe to output.
    def secret_to_dict(s: SecretStatus) -> dict:  # nosec B105 - metadata only, no credentials
        return {
            "id": s.id,
            "name": s.name,
            "project": s.project,
            "location": s.location,
            "policy": s.policy,
            "last_rotated": s.last_rotated.isoformat() if s.last_rotated else None,
            "next_rotation": s.next_rotation.isoformat() if s.next_rotation else None,
            "days_until": s.days_until,
            "owner": s.owner,
            "risk_level": s.risk_level,
            "procedure": s.procedure,
            "status": s.status,
            "dependencies": s.dependencies
        }

    output = {
        "report_date": date.today().isoformat(),
        "has_overdue": len(overdue) > 0,
        "has_upcoming": len(due_soon) + len(upcoming) > 0,
        "summary": {
            "overdue_count": len(overdue),
            "due_soon_count": len(due_soon),
            "upcoming_count": len(upcoming)
        },
        "overdue": [secret_to_dict(s) for s in overdue],
        "due_soon": [secret_to_dict(s) for s in due_soon],
        "upcoming": [secret_to_dict(s) for s in upcoming]
    }

    return json.dumps(output, indent=2)


def format_slack_message(overdue: list, due_soon: list, upcoming: list) -> str:
    """Format Slack-compatible message."""
    blocks = []
    today = date.today().isoformat()

    # Header
    if overdue:
        header = f"🚨 *SECRETS ROTATION ALERT* - {today}"
    elif due_soon:
        header = f"⚠️ *Secrets Rotation Reminder* - {today}"
    else:
        header = f"✅ *Secrets Status OK* - {today}"

    blocks.append(header)
    blocks.append("")

    # Overdue
    if overdue:
        blocks.append("*OVERDUE - Immediate Action Required:*")
        for s in overdue:
            blocks.append(f"• `{s.id}` ({s.project}) - {abs(s.days_until)} days overdue")
            blocks.append(f"  Owner: {s.owner} | Procedure: {s.procedure}")
        blocks.append("")

    # Due soon
    if due_soon:
        blocks.append("*Due within 3 days:*")
        for s in due_soon:
            blocks.append(f"• `{s.id}` ({s.project}) - {s.days_until} days")
        blocks.append("")

    # Summary
    blocks.append(f"_Total: {len(overdue)} overdue, {len(due_soon)} due soon, {len(upcoming)} upcoming_")

    return "\n".join(blocks)


def format_github_output(overdue: list, due_soon: list, upcoming: list) -> str:
    """Format GitHub Actions output variables."""
    lines = []

    lines.append(f"has_overdue={'true' if overdue else 'false'}")
    lines.append(f"has_upcoming={'true' if (due_soon or upcoming) else 'false'}")
    lines.append(f"overdue_count={len(overdue)}")
    lines.append(f"due_soon_count={len(due_soon)}")
    lines.append(f"upcoming_count={len(upcoming)}")

    # List of overdue secret IDs for issue creation
    overdue_ids = ",".join(s.id for s in overdue)
    lines.append(f"overdue_list={overdue_ids}")

    # Formatted report for Slack
    slack_report = format_slack_message(overdue, due_soon, upcoming)
    # Escape for GitHub Actions (replace newlines)
    escaped_report = slack_report.replace("\n", "%0A").replace("\r", "%0D")
    lines.append(f"report={escaped_report}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Check MADFAM secrets rotation schedule"
    )
    parser.add_argument(
        "--output",
        choices=["text", "json", "slack", "github"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--slack-format",
        action="store_true",
        help="Shorthand for --output slack"
    )
    parser.add_argument(
        "--github-format",
        action="store_true",
        help="Shorthand for --output github"
    )
    parser.add_argument(
        "--registry",
        type=Path,
        help="Path to SECRETS_REGISTRY.yaml"
    )

    args = parser.parse_args()

    # Handle format shortcuts
    if args.slack_format:
        args.output = "slack"
    elif args.github_format:
        args.output = "github"

    try:
        registry_path = args.registry if args.registry else find_registry_path()
        overdue, due_soon, upcoming = check_rotations(registry_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except yaml.YAMLError as e:
        print(f"ERROR: Failed to parse registry YAML: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    # Output based on format
    if args.output == "json":
        print(format_json_output(overdue, due_soon, upcoming))
    elif args.output == "slack":
        print(format_slack_message(overdue, due_soon, upcoming))
    elif args.output == "github":
        output = format_github_output(overdue, due_soon, upcoming)
        # Write to GITHUB_OUTPUT if available
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write(output + "\n")
        print(output)
    else:
        print(format_text_report(overdue, due_soon, upcoming))

    # Exit code based on status
    if overdue:
        sys.exit(1)  # CRITICAL: has overdue secrets
    sys.exit(0)


if __name__ == "__main__":
    main()
