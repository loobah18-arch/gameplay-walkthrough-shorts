import unittest
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


if __name__ == "__main__":
    unittest.main()
