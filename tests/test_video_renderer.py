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

    def test_build_ffmpeg_filtergraph_square(self):
        fg = VideoRenderer.build_ffmpeg_filtergraph(
            aspect_ratio="square",
            ass_subtitle_path=None,
            apply_enhancements=True,
        )
        self.assertIn("crop=1080:1080", fg)
        self.assertIn("unsharp=", fg)
        self.assertIn("eq=contrast=", fg)

    def test_build_ffmpeg_filtergraph_vertical_blurred(self):
        fg = VideoRenderer.build_ffmpeg_filtergraph(
            aspect_ratio="vertical_blurred",
            ass_subtitle_path=None,
            apply_enhancements=False,
        )
        self.assertIn("boxblur=", fg)
        self.assertIn("overlay=", fg)

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
