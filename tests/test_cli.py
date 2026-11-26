import argparse
import sys
import unittest
from unittest.mock import MagicMock, patch
import cli


class TestCLI(unittest.TestCase):
    def test_parse_timestamp_arg(self):
        self.assertEqual(cli.parse_timestamp_arg("5964"), 5964.0)
        self.assertEqual(cli.parse_timestamp_arg("01:39:24"), 5964.0)
        self.assertEqual(cli.parse_timestamp_arg("02:30.5"), 150.5)
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.parse_timestamp_arg("-5")
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.parse_timestamp_arg("nan")
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.parse_timestamp_arg("inf")
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.parse_timestamp_arg("abc")

    def test_render_cloud_job_enable_subtitles_defaults_false(self):
        with patch.object(sys, "argv", ["cli.py", "render-cloud-job", "--url", "https://youtu.be/abc123", "--start", "0", "--end", "10"]):
            parser_args = None
            def capture(args):
                nonlocal parser_args
                parser_args = args
            with patch("cli.cmd_render_cloud_job", side_effect=capture):
                cli.main()
            self.assertFalse(parser_args.enable_subtitles)

        with patch.object(sys, "argv", ["cli.py", "render-cloud-job", "--url", "https://youtu.be/abc123", "--start", "0", "--end", "10", "--enable-subtitles"]):
            parser_args = None
            def capture(args):
                nonlocal parser_args
                parser_args = args
            with patch("cli.cmd_render_cloud_job", side_effect=capture):
                cli.main()
            self.assertTrue(parser_args.enable_subtitles)

    def test_validate_cookies_missing_file_exits_instead_of_fallback(self):
        args = argparse.Namespace(file="/tmp/does_not_exist_12345.txt", secret=None, export=None)
        with self.assertRaises(SystemExit) as ctx:
            cli.cmd_validate_cookies(args)
        self.assertEqual(ctx.exception.code, 1)

    def test_validate_cookies_whitespace_secret_exits_cleanly(self):
        args = argparse.Namespace(file=None, secret="   ", export=None)
        with self.assertRaises(SystemExit) as ctx:
            cli.cmd_validate_cookies(args)
        self.assertEqual(ctx.exception.code, 1)

    def test_select_verified_cutscene_rejects_short_and_no_payoff_candidates(self):
        crawler = MagicMock()
        crawler.is_previously_clipped.return_value = False
        analyzer = cli.CutsceneAnalyzer()

        # Candidate under 180s (Short) -> rejected even without chapters
        fetcher_short = MagicMock()
        fetcher_short.fetch_video_info.return_value = {"duration": 45, "chapters": []}
        short_cand = {"video_id": "s1", "title": "Short Clip", "url": "https://youtu.be/s1", "game_name": "GTA V"}
        self.assertIsNone(cli._select_verified_cutscene(short_cand, fetcher_short, analyzer, crawler))

        # Long candidate with only gameplay chapter & no transcript payoff -> rejected (never falls back to 60-115s)
        fetcher_gameplay = MagicMock()
        fetcher_gameplay.fetch_video_info.return_value = {
            "duration": 600,
            "chapters": [{"title": "Free Roam Driving", "start_time": 0, "end_time": 300}],
        }
        fetcher_gameplay.fetch_transcript.return_value = []
        gp_cand = {"video_id": "gp1", "title": "Gameplay Only", "url": "https://youtu.be/gp1", "game_name": "GTA V"}
        self.assertIsNone(cli._select_verified_cutscene(gp_cand, fetcher_gameplay, analyzer, crawler))

        # Valid cutscene chapter -> accepted
        fetcher_valid = MagicMock()
        fetcher_valid.fetch_video_info.return_value = {
            "duration": 900,
            "chapters": [{"title": "Devin Weston Cliff Cutscene Ending", "start_time": 100, "end_time": 180}],
            "age_limit": 0,
        }
        valid_cand = {"video_id": "v1", "title": "Full Movie", "url": "https://youtu.be/v1", "game_name": "GTA V"}
        picked = cli._select_verified_cutscene(valid_cand, fetcher_valid, analyzer, crawler)
        self.assertIsNotNone(picked)
        self.assertEqual(picked["scene_title"], "Devin Weston Cliff Cutscene Ending")
        self.assertGreaterEqual(picked["start"], 100)

        # Age-restricted candidate -> rejected
        fetcher_age = MagicMock()
        fetcher_age.fetch_video_info.return_value = {
            "duration": 900,
            "chapters": [{"title": "Devin Weston Cliff Cutscene Ending", "start_time": 100, "end_time": 180}],
            "age_limit": 18,
        }
        self.assertIsNone(cli._select_verified_cutscene(valid_cand, fetcher_age, analyzer, crawler))


if __name__ == "__main__":
    unittest.main()
