import os
import unittest
from core.video_renderer import VideoRenderer


class TestVideoRenderer(unittest.TestCase):
    def test_build_ytdlp_download_cmd(self):
        cmd = VideoRenderer.build_ytdlp_download_cmd(
            video_url="https://youtube.com/watch?v=12345",
            start_time=120.0,
            end_time=175.0,
            output_filepath="temp/raw.mp4",
            cookies_path="cookies.txt",
            proxy="http://user:pass@proxy.example.com:8080",
            po_token="test_po_token_123",
            visitor_data="test_visitor_data_456",
        )
        self.assertIn("--download-sections", cmd)
        self.assertIn("*00:02:00-00:02:55", cmd)
        self.assertIn("--cookies", cmd)
        self.assertIn("cookies.txt", cmd)
        self.assertIn("--proxy", cmd)
        self.assertIn("http://user:pass@proxy.example.com:8080", cmd)
        self.assertIn("https://youtube.com/watch?v=12345", cmd)
        self.assertIn("youtube:po_token=web.gvs+test_po_token_123", cmd)
        self.assertIn("youtube:visitor_data=test_visitor_data_456", cmd)

        # Redaction check
        logged = VideoRenderer._redact_cmd_for_log(cmd)
        self.assertNotIn("user:pass", logged)
        self.assertNotIn("test_po_token_123", logged)
        self.assertNotIn("test_visitor_data_456", logged)

    def test_fractional_hms_and_mobile_env_isolation(self):
        old_pot = os.environ.get("YT_PO_TOKEN")
        os.environ["YT_PO_TOKEN"] = "env_web_token"
        try:
            cmd = VideoRenderer.build_ytdlp_download_cmd(
                video_url="https://youtube.com/watch?v=12345",
                start_time=120.25,
                end_time=175.5,
                client_override="visionos",
                use_cookies=False,
            )
            self.assertIn("*00:02:00.250-00:02:55.500", cmd)
            self.assertNotIn("env_web_token", " ".join(cmd))
        finally:
            if old_pot is None:
                os.environ.pop("YT_PO_TOKEN", None)
            else:
                os.environ["YT_PO_TOKEN"] = old_pot

    def test_build_ffmpeg_filtergraph_square(self):
        fg = VideoRenderer.build_ffmpeg_filtergraph(
            aspect_ratio="square",
            ass_subtitle_path=None,
            apply_enhancements=True,
        )
        self.assertIn("scale=1080:1080:force_original_aspect_ratio=increase", fg)
        self.assertIn("crop=1080:1080", fg)
        self.assertIn("unsharp=", fg)
        self.assertIn("eq=contrast=", fg)

    def test_build_ffmpeg_filtergraph_vertical_blurred(self):
        fg = VideoRenderer.build_ffmpeg_filtergraph(
            aspect_ratio="vertical_blurred",
            ass_subtitle_path=None,
            apply_enhancements=True,
        )
        self.assertIn("boxblur=", fg)
        self.assertIn("overlay=", fg)
        self.assertIn("unsharp=", fg)

    def test_escape_ffmpeg_ass_path(self):
        escaped = VideoRenderer._escape_ffmpeg_ass_path("C:\\tmp\\foo's:bar[1].ass")
        self.assertIn("\\\\\\'", escaped)
        self.assertIn("\\\\\\:", escaped)
        self.assertIn("\\[1\\]", escaped)

    def test_build_ffmpeg_render_cmd(self):
        cmd = VideoRenderer.build_ffmpeg_render_cmd(
            raw_input="raw.mp4",
            output_file="final.mp4",
            aspect_ratio="square",
            ass_subtitle_path=None,
            apply_enhancements=True,
            normalize_audio=True,
        )
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-vf", cmd)
        self.assertIn("-af", cmd)
        self.assertIn("loudnorm=", " ".join(cmd))
        self.assertIn("final.mp4", cmd)


if __name__ == "__main__":
    unittest.main()
