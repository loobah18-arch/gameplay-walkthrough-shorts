import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from core.candle_gate import CandleGate
from core.preflight_gate import decide
from core.schedule_updater import calculate_next_schedule, update_workflow_cron


class TestSafetyAndSchedule(unittest.TestCase):
    def test_preflight_blocks_within_24h_with_zero_sleep(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = Path(tmp) / "upload_history.json"
            now = datetime(2026, 11, 26, 12, 0, 0, tzinfo=timezone.utc)
            last_upload = now - timedelta(hours=10)
            hist.write_text(json.dumps([{
                "timestamp": last_upload.isoformat(),
                "youtube_id": "yt123",
                "published": True,
                "status": "published",
            }]))

            res = decide(history_path=hist, now=now)
            self.assertFalse(res["proceed"])
            self.assertEqual(res["elapsed_hours"], 10.0)
            self.assertGreater(res["remaining_seconds"], 0)
            # Due time is 24h + 2m after last_upload -> 02:02 UTC next day
            self.assertEqual(res["next_cron"], "2 2 * * *")

    def test_preflight_clears_after_24h_unless_live_velocity_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = Path(tmp) / "upload_history.json"
            now = datetime(2026, 11, 26, 12, 0, 0, tzinfo=timezone.utc)
            last_upload = now - timedelta(hours=25)
            hist.write_text(json.dumps([{
                "timestamp": last_upload.isoformat(),
                "youtube_id": "yt123",
                "published": True,
                "status": "published",
            }]))

            # Without live client -> cleared
            res = decide(history_path=hist, now=now)
            self.assertTrue(res["proceed"])

            # With mock client reporting viral velocity (>2500/hr) -> blocked by Layer 2
            mock_yt = MagicMock()
            mock_yt.videos().list().execute.return_value = {
                "items": [{
                    "snippet": {"title": "Cutscene", "publishedAt": last_upload.isoformat()},
                    "statistics": {"viewCount": "100000"},
                }]
            }
            state_path = Path(tmp) / "candle_state.json"
            res_live = decide(history_path=hist, now=now, youtube_client=mock_yt, state_file=state_path)
            self.assertFalse(res_live["proceed"])

    def test_schedule_updater_writes_exact_cron(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = Path(tmp) / "upload_history.json"
            wf = Path(tmp) / "daily.yml"
            now = datetime(2026, 11, 26, 10, 0, 0, tzinfo=timezone.utc)
            last_upload = datetime(2026, 11, 25, 14, 40, 0, tzinfo=timezone.utc)
            hist.write_text(json.dumps([{
                "timestamp": last_upload.isoformat(),
                "youtube_id": "yt999",
                "published": True,
                "status": "published",
            }]))
            wf.write_text("on:\n  schedule:\n    - cron: '0 * * * *'\n")

            info = calculate_next_schedule(history_path=hist, now=now)
            self.assertEqual(info["cron"], "42 14 * * *")
            self.assertTrue(update_workflow_cron(wf, info["cron"]))
            self.assertIn("- cron: '42 14 * * *'", wf.read_text())
            self.assertFalse(update_workflow_cron(wf, info["cron"]))

    def test_candle_gate_layers(self):
        gate = CandleGate()
        l1 = gate.evaluate_early_momentum(total_views=2500, elapsed_hours=10.0)
        self.assertFalse(l1["can_upload"])
        l2 = gate.evaluate_hourly_candles([1000, 3000] + [1500] * 24)
        self.assertTrue(l2["can_upload"])


if __name__ == "__main__":
    unittest.main()
