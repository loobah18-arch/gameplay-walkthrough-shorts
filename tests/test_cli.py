import argparse
import sys
import unittest
from unittest.mock import patch
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


if __name__ == "__main__":
    unittest.main()
