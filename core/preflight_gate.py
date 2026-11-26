#!/usr/bin/env python3
"""
Algorithm Safety Pre-flight Gate (Layer 0, Layer 1 & Layer 2).

Uses CandleGate to evaluate upload readiness cleanly with ZERO runner sleeping:
  - Layer 0 (24h Spacing): blocks if < 24.0h elapsed since the last published upload.
  - Layer 1 & Layer 2 (Live Channel Telemetry): when YouTube OAuth credentials exist,
    blocks if the latest Short crossed >= 2k views in 24h or >= 2.5k views/hr velocity.
  - Fail-open on missing history / unconfigured credentials so initial runs proceed.

Manual workflow_dispatch runs set PREFLIGHT_BYPASS to always proceed.
Exit code is always 0; `proceed` and `next_cron` are exported via GITHUB_OUTPUT.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from core.candle_gate import CandleGate
    from core.youtube_uploader import build_youtube_client
except ImportError:
    from candle_gate import CandleGate
    build_youtube_client = None

DEFAULT_HISTORY = Path(__file__).resolve().parent.parent / "upload_history.json"
DEFAULT_MIN_SPACING_HOURS = 24.0


def _parse_timestamp(raw: str) -> datetime:
    ts = raw.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _last_valid_upload(records: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Returns the latest entry representing an actual published YouTube upload."""
    for rec in reversed(records if isinstance(records, list) else []):
        if not isinstance(rec, dict):
            continue
        vid = str(rec.get("video_id") or rec.get("youtube_id") or "")
        if not vid or vid.startswith("dry_run"):
            if not rec.get("published", False) and rec.get("status") not in {"uploaded", "published"}:
                continue
        elif rec.get("status") not in {"uploaded", "published"} and not rec.get("published", False):
            continue
        raw_ts = rec.get("timestamp")
        if not raw_ts or not isinstance(raw_ts, str):
            continue
        return rec, raw_ts
    return None, None


def check_preflight_gate(history_file=DEFAULT_HISTORY, min_hours: float = DEFAULT_MIN_SPACING_HOURS) -> bool:
    """Convenience wrapper returning boolean for CLI callers."""
    res = decide(history_path=history_file, min_spacing_hours=min_hours)
    return bool(res.get("proceed", True))


def decide(
    history_path=DEFAULT_HISTORY,
    now: Optional[datetime] = None,
    min_spacing_hours: float = DEFAULT_MIN_SPACING_HOURS,
    youtube_client=None,
    state_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Pure zero-sleep decision function evaluating Layer 0 spacing and optional
    Layer 1/2 live channel velocity.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    try:
        history = Path(history_path)
        records = json.loads(history.read_text(encoding="utf-8")) if history.exists() else []
    except Exception as exc:
        return {
            "proceed": True,
            "elapsed_hours": None,
            "last_video_id": None,
            "remaining_seconds": 0,
            "due_at": "",
            "next_cron": "0 * * * *",
            "reason": f"fail-open: unreadable history ({exc})",
        }

    rec, raw_ts = _last_valid_upload(records)
    if rec is None or not raw_ts:
        return {
            "proceed": True,
            "elapsed_hours": None,
            "last_video_id": None,
            "remaining_seconds": 0,
            "due_at": "",
            "next_cron": "0 * * * *",
            "reason": "no prior published upload found; pipeline cleared",
        }

    try:
        published_at = _parse_timestamp(raw_ts)
    except Exception as exc:
        return {
            "proceed": True,
            "elapsed_hours": None,
            "last_video_id": rec.get("video_id") or rec.get("youtube_id"),
            "remaining_seconds": 0,
            "due_at": "",
            "next_cron": "0 * * * *",
            "reason": f"fail-open: unparseable timestamp {raw_ts!r} ({exc})",
        }

    vid = rec.get("video_id") or rec.get("youtube_id")
    elapsed_hours = max((now - published_at).total_seconds() / 3600.0, 0.0)
    gate = CandleGate(state_file=Path(state_file)) if state_file else CandleGate()

    # Zero-sleep evaluation: max_inline_wait_hours=0.0 prevents any runner sleep
    spacing = gate.evaluate_upload_spacing(elapsed_hours, min_spacing_hours, max_inline_wait_hours=0.0)
    due_at = published_at + timedelta(hours=min_spacing_hours, minutes=2)
    next_cron = f"{due_at.minute} {due_at.hour} * * *"

    base = {
        "elapsed_hours": round(elapsed_hours, 2),
        "last_video_id": vid,
        "next_cron": next_cron,
    }

    if not spacing["can_upload"]:
        remaining = max(int(round((min_spacing_hours - elapsed_hours) * 3600)), 0)
        return {
            **base,
            "proceed": False,
            "remaining_seconds": remaining,
            "due_at": due_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reason": spacing["recommendation"],
        }

    # Layer 1 & Layer 2: check live YouTube telemetry when authenticated client is provided
    if youtube_client is not None:
        live = gate.evaluate_live_channel(youtube_client=youtube_client, history_path=Path(history_path))
        candle_eval = live.get("candle_evaluation", {})
        if candle_eval and not candle_eval.get("can_upload", True):
            return {
                **base,
                "proceed": False,
                "remaining_seconds": int(candle_eval.get("timer_seconds", 3600)),
                "due_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "next_cron": f"{(now + timedelta(hours=1)).minute} {(now + timedelta(hours=1)).hour} * * *",
                "reason": candle_eval.get("recommendation", "Blocked by Candle Gate Layer 1/2"),
            }

    return {
        **base,
        "proceed": True,
        "remaining_seconds": 0,
        "due_at": "",
        "reason": spacing["recommendation"],
    }


def main() -> int:
    bypass = (
        os.environ.get("PREFLIGHT_BYPASS", "").strip().lower() in {"1", "true", "yes"}
        or "--bypass" in sys.argv
    )

    if bypass:
        result = {
            "proceed": True,
            "elapsed_hours": None,
            "last_video_id": None,
            "remaining_seconds": 0,
            "due_at": "",
            "next_cron": "0 * * * *",
            "reason": "PREFLIGHT_BYPASS set (manual dispatch) — spacing gate bypassed",
        }
    else:
        yt_client = None
        if build_youtube_client is not None:
            try:
                yt_client = build_youtube_client()
            except Exception as exc:
                print(f"⚠️ Skipping live Layer 1/2 check ({exc}); evaluating Layer 0 history only.")
        try:
            result = decide(youtube_client=yt_client)
        except Exception as exc:
            result = {
                "proceed": True,
                "elapsed_hours": None,
                "last_video_id": None,
                "remaining_seconds": 0,
                "due_at": "",
                "next_cron": "0 * * * *",
                "reason": f"fail-open: unexpected gate error ({exc})",
            }

    icon = "✅ PROCEED" if result["proceed"] else "🛑 SKIP"
    print(f"{icon} | elapsed={result['elapsed_hours']}h | last_upload={result['last_video_id']}")
    if not result["proceed"] and result.get("due_at"):
        print(f"⏰ Next upload due at {result['due_at']} (cron: '{result.get('next_cron')}')")
    print(result["reason"])

    out_file = os.environ.get("GITHUB_OUTPUT")
    if out_file:
        with open(out_file, "a", encoding="utf-8") as f:
            f.write(f"proceed={'true' if result['proceed'] else 'false'}\n")
            f.write(f"remaining_seconds={result.get('remaining_seconds', 0)}\n")
            f.write(f"due_at={result.get('due_at', '')}\n")
            f.write(f"next_cron={result.get('next_cron', '0 * * * *')}\n")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(
                f"### 🕯️ Algorithm Safety Pre-flight (Zero-Sleep)\n\n"
                f"{icon} — elapsed **{result['elapsed_hours']}h** since last upload "
                f"(`{result['last_video_id']}`)\n\n> {result['reason']}\n"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
