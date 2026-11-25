import unittest
from core.cloud_dispatcher import CloudDispatcher


class TestCloudDispatcher(unittest.TestCase):
    def test_generate_clip_spec(self):
        dispatcher = CloudDispatcher(repo="test-owner/test-repo")
        spec = dispatcher.generate_clip_spec(
            video_url="https://youtube.com/watch?v=abcde",
            start_time=60.0,
            end_time=115.0,
            title="Connor Deviancy Test",
            game_name="Detroit: Become Human",
            aspect_ratio="square",
            enable_subtitles=True,
        )
        self.assertEqual(spec["duration"], 55.0)
        self.assertEqual(spec["aspect_ratio"], "square")
        self.assertEqual(spec["title"], "Connor Deviancy Test")

    def test_invalid_time_range_raises(self):
        dispatcher = CloudDispatcher()
        with self.assertRaises(ValueError):
            dispatcher.generate_clip_spec("https://youtube.com/watch?v=abcde", 50.0, 20.0, "Bad")
        with self.assertRaises(ValueError):
            dispatcher.generate_clip_spec("https://youtube.com/watch?v=abcde", -5.0, 20.0, "Neg")

    def test_get_dispatch_command_escapes_shell_metachars(self):
        dispatcher = CloudDispatcher(repo="loobah18-arch/gameplay-walkthrough-shorts")
        spec = dispatcher.generate_clip_spec(
            video_url="https://youtube.com/watch?v=abcde",
            start_time=60.0,
            end_time=115.0,
            title='Connor said "$(whoami)" `id`',
            game_name="Detroit",
            aspect_ratio="square",
        )
        cmd = dispatcher.get_dispatch_command(spec)
        self.assertIn("gh workflow run", cmd)
        self.assertIn("--repo loobah18-arch/gameplay-walkthrough-shorts", cmd)
        self.assertIn('-f aspect_ratio="square"', cmd)
        self.assertIn('\\$(whoami)', cmd)
        self.assertIn('\\`id\\`', cmd)
        self.assertIn('\\"', cmd)

    def test_dispatch_dry_run(self):
        dispatcher = CloudDispatcher()
        spec = dispatcher.generate_clip_spec(
            video_url="https://youtube.com/watch?v=abcde",
            start_time=0.0,
            end_time=50.0,
            title="Sample",
        )
        res = dispatcher.dispatch(spec, dry_run=True)
        self.assertEqual(res["status"], "ready")
        self.assertEqual(res["mode"], "dry_run")


if __name__ == "__main__":
    unittest.main()
