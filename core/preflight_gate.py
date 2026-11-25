"""
24-Hour Spacing Pre-flight Gate & Algorithm Safety Layer.
Prevents YouTube spam detection by strictly enforcing >= 24.0 hours between uploads.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from config.settings import ROOT_DIR

UPLOAD_HISTORY_PATH = os.path.join(ROOT_DIR, "upload_history.json")
MIN_SPACING_HOURS = 24.0


def parse_timestamp(iso_str: str) -> datetime:
    """Parses ISO timestamp string to UTC datetime."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def check_preflight_gate(history_file: str = UPLOAD_HISTORY_PATH, min_hours: float = MIN_SPACING_HOURS) -> bool:
    """
    Checks if >= 24.0 hours have elapsed since the last upload.
    Returns True if gate passes, False if in cooldown.
    """
    if not os.path.isfile(history_file):
        print(f"✅ Pre-flight Gate PASSED: No previous upload history found at {history_file}.")
        return True

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            entries = data if isinstance(data, list) else data.get("entries", [])
    except Exception as e:
        print(f"⚠️ Warning: Could not parse {history_file} ({e}). Allowing run.")
        return True

    if not entries:
        print("✅ Pre-flight Gate PASSED: History is empty. Ready for initial upload.")
        return True

    # Find the most recent entry with a valid timestamp
    recent_entry = None
    for entry in reversed(entries):
        if entry.get("timestamp"):
            recent_entry = entry
            break

    if not recent_entry:
        print("✅ Pre-flight Gate PASSED: No timestamped prior runs.")
        return True

    last_time = parse_timestamp(recent_entry["timestamp"])
    now = datetime.now(timezone.utc)
    elapsed = (now - last_time).total_seconds() / 3600.0

    print(f"🕒 Last upload: {recent_entry.get('title', 'Unknown')} at {recent_entry['timestamp']}")
    print(f"⏳ Time elapsed: {elapsed:.2f} hours (Required spacing: {min_hours:.1f} hours)")

    if elapsed < min_hours:
        remaining = min_hours - elapsed
        print(f"⏸️ Pre-flight Gate CLOSED: Cooldown active ({remaining:.2f} hours remaining). Skipping pipeline.")
        return False

    print("✅ Pre-flight Gate PASSED: >= 24.0 hours elapsed. Algorithmic pacing safe.")
    return True


if __name__ == "__main__":
    passed = check_preflight_gate()
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output and os.path.isfile(github_output):
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"gate_passed={'true' if passed else 'false'}\n")
    sys.exit(0 if passed else 1)
