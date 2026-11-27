import json
import subprocess
import unittest
from unittest.mock import patch, MagicMock
from core.walkthrough_fetcher import WalkthroughFetcher


class TestWalkthroughFetcher(unittest.TestCase):
    def test_parse_timestamp(self):
        self.assertEqual(WalkthroughFetcher.parse_timestamp("00:01:23.456"), 83.456)
        self.assertEqual(WalkthroughFetcher.parse_timestamp("02:15.000"), 135.0)
        self.assertEqual(WalkthroughFetcher.parse_timestamp("45.5"), 45.5)

    def test_parse_vtt_content(self):
        sample_vtt = """WEBVTT
Kind: captions
Language: en

00:00:10.000 --> 00:00:14.500
<c>Connor:</c> Are you afraid of death?

00:00:14.500 --> 00:00:19.000
Machines don't feel anything.

00:00:19.000 --> 00:00:23.000
Machines don't feel anything.

00:00:23.000 --> 00:00:28.000
I am just a machine, not a living being.
"""
        cues = WalkthroughFetcher.parse_vtt_content(sample_vtt)
        self.assertEqual(len(cues), 3)
        self.assertEqual(cues[0]["start"], 10.0)
        self.assertEqual(cues[0]["end"], 14.5)
        self.assertIn("Are you afraid of death?", cues[0]["text"])
        self.assertEqual(cues[1]["text"], "Machines don't feel anything.")
        self.assertEqual(cues[2]["text"], "I am just a machine, not a living being.")

    def test_parse_vtt_crlf_entities_note_and_cue_ids(self):
        sample_vtt = (
            "WEBVTT\r\n\r\n"
            "NOTE comment with --> arrow should be ignored\r\n\r\n"
            "cue-1\r\n"
            "0:01:02.500 --> 0:01:05.000 align:start\r\n"
            "I don&#39;t care &amp; I won&apos;t stop!\r\n\r\n"
            "0:01:05.000 --> 0:01:05.010\r\n"
            "I won't stop!\r\n"
        )
        cues = WalkthroughFetcher.parse_vtt_content(sample_vtt)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0]["start"], 62.5)
        self.assertEqual(cues[0]["text"], "I don't care & I won't stop!")

    @patch("core.walkthrough_fetcher.CookieManager.get_ytdlp_cookie_args", return_value=["--cookies", "c.txt"])
    @patch("core.walkthrough_fetcher.subprocess.run")
    def test_fetch_video_info_preserves_proxy_on_fallback_and_null_duration(self, mock_run, _mock_cookies):
        payload = json.dumps({"id": "vid123", "title": "Test", "duration": None, "formats": []})
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "yt-dlp"),
            MagicMock(stdout=payload, returncode=0),
        ]
        fetcher = WalkthroughFetcher()
        info = fetcher.fetch_video_info("https://youtube.com/watch?v=vid123", proxy="http://proxy:8080")
        self.assertEqual(info["duration"], 0)
        primary_cmd = mock_run.call_args_list[0].args[0]
        self.assertIn("--no-cookies", primary_cmd)
        fallback_cmd = mock_run.call_args_list[1].args[0]
        self.assertIn("--proxy", fallback_cmd)
        self.assertIn("http://proxy:8080", fallback_cmd)

    @patch("core.walkthrough_fetcher.glob.glob", return_value=[])
    @patch("core.walkthrough_fetcher.subprocess.run")
    def test_fetch_transcript_tries_mobile_clients_before_web_bgutil(self, mock_run, _mock_glob):
        mock_run.return_value = MagicMock(returncode=1, stderr="no subs")
        fetcher = WalkthroughFetcher()
        cues = fetcher.fetch_transcript("https://youtube.com/watch?v=vid123", "vid123")
        self.assertEqual(cues, [])
        first_cmd = mock_run.call_args_list[0].args[0]
        second_cmd = mock_run.call_args_list[1].args[0]
        self.assertIn("youtube:player_client=ios,android_vr", first_cmd)
        self.assertIn("youtube:player_client=web,mweb", second_cmd)
        self.assertTrue(any("youtubepot-bgutilhttp:base_url=" in a for a in second_cmd))

    def test_parse_chapters_from_description(self):
        desc = """All Cutscenes Timestamps:
00:00 Opening Scene
05:30 Final Confrontation
12:45 Ending Choice
"""
        chapters = WalkthroughFetcher.parse_chapters_from_description(desc, total_duration=900.0)
        self.assertEqual(len(chapters), 3)
        self.assertEqual(chapters[1]["title"], "Final Confrontation")
        self.assertEqual(chapters[1]["start_time"], 330.0)
        self.assertEqual(chapters[1]["end_time"], 765.0)
        self.assertEqual(chapters[2]["end_time"], 900.0)


if __name__ == "__main__":
    unittest.main()
