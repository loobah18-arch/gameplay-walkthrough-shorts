#!/usr/bin/env python3
"""
Dynamic Schedule Calculator & Workflow Cron Updater.

Calculates the exact UTC timestamp when the 24-hour upload cooldown expires
from upload_history.json and updates the GitHub Actions workflow cron schedule
to trigger at that exact minute — eliminating runner sleeps.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from core.preflight_gate import _last_valid_upload, _parse_timestamp
except ImportError:
    from preflight_gate import _last_valid_upload, _parse_timestamp

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY = ROOT / "upload_history.json"
DEFAULT_WORKFLOW = ROOT / ".github" / "workflows" / "daily_walkthrough_short.yml"
FALLBACK_HOURLY_CRON = "0 * * * *"


def calculate_next_schedule(
    history_path: Path = DEFAULT_HISTORY,
    min_spacing_hours: float = 24.0,
    buffer_minutes: int = 2,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Computes the next eligible upload time and exact UTC cron expression.
    Adds a small buffer (default +2m) so GitHub's scheduler wakes past 24.0h.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    try:
        records = json.loads(Path(history_path).read_text(encoding="utf-8")) if Path(history_path).exists() else []
    except Exception:
        records = []

    rec, raw_ts = _last_valid_upload(records)
    if rec is None or not raw_ts:
        return {
            "has_prior_upload": False,
            "is_due": True,
            "remaining_seconds": 0,
            "due_at": None,
            "cron": FALLBACK_HOURLY_CRON,
            "reason": "No published upload in history; using hourly check cron.",
        }

    try:
        published_at = _parse_timestamp(raw_ts)
    except Exception:
        return {
            "has_prior_upload": True,
            "is_due": True,
            "remaining_seconds": 0,
            "due_at": None,
            "cron": FALLBACK_HOURLY_CRON,
            "reason": "Unparseable timestamp; using hourly check cron.",
        }

    due_at = published_at + timedelta(hours=min_spacing_hours, minutes=buffer_minutes)
    remaining_seconds = max(int(round((due_at - now).total_seconds())), 0)
    is_due = now >= due_at

    # Target the exact UTC minute & hour for tomorrow's run
    cron_expr = f"{due_at.minute} {due_at.hour} * * *"

    return {
        "has_prior_upload": True,
        "last_upload_at": published_at.isoformat(),
        "due_at": due_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "remaining_seconds": remaining_seconds,
        "is_due": is_due,
        "cron": cron_expr,
        "reason": f"Next upload calculated for {due_at.strftime('%Y-%m-%d %H:%M UTC')} (cron: '{cron_expr}').",
    }


def update_workflow_cron(workflow_path: Path = DEFAULT_WORKFLOW, cron_expr: str = FALLBACK_HOURLY_CRON) -> bool:
    """
    Updates the `- cron: '...'` trigger inside daily_walkthrough_short.yml in-place.
    Returns True if file contents changed, False otherwise.
    """
    path = Path(workflow_path)
    if not path.is_file():
        return False

    original = path.read_text(encoding="utf-8")
    pattern = re.compile(r"(on:\s*\n\s*schedule:\s*\n(?:[ \t]*#.*\n)*[ \t]*-\s*cron:\s*)'[^']*'")
    if not pattern.search(original):
        return False

    updated = pattern.sub(rf"\g<1>'{cron_expr}'", original, count=1)
    if updated == original:
        return False

    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate exact next upload cron from upload_history.json")
    parser.add_argument("--history", default=str(DEFAULT_HISTORY), help="Path to upload_history.json")
    parser.add_argument("--workflow", default=str(DEFAULT_WORKFLOW), help="Path to workflow YAML")
    parser.add_argument("--apply", action="store_true", help="Write calculated cron back to workflow YAML")
    args = parser.parse_args()

    info = calculate_next_schedule(history_path=Path(args.history))
    print(f"📅 {info['reason']}")

    changed = False
    if args.apply:
        changed = update_workflow_cron(Path(args.workflow), info["cron"])
        status = f"updated workflow cron to '{info['cron']}'" if changed else f"workflow cron already '{info['cron']}'"
        print(f"📝 {status}")

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"cron={info['cron']}\n")
            f.write(f"due_at={info.get('due_at') or ''}\n")
            f.write(f"changed={'true' if changed else 'false'}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
