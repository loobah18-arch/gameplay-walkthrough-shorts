import unittest
import os
import tempfile
from core.subtitle_builder import SubtitleBuilder


class TestSubtitleBuilder(unittest.TestCase):
    def test_format_ass_time(self):
        self.assertEqual(SubtitleBuilder.format_ass_time(0.0), "0:00:00.00")
        self.assertEqual(SubtitleBuilder.format_ass_time(65.25), "0:01:05.25")
        self.assertEqual(SubtitleBuilder.format_ass_time(3661.5), "1:01:01.50")
        self.assertEqual(SubtitleBuilder.format_ass_time(59.999), "0:01:00.00")

    def test_highlight_text(self):
        text = "Connor is just a machine, not a living being!"
        highlighted = SubtitleBuilder.highlight_text(text, keywords=["machine", "living being", "alive"])
        self.assertIn("machine", highlighted)
        self.assertIn("living being", highlighted)
        # Ensure Bold=1 is restored after highlights instead of turning bold off (\b0)
        self.assertNotIn("\\b0", highlighted)
        self.assertIn("\\b1", highlighted)

    def test_generate_ass_file(self):
        with tempfile.TemporaryDirectory() as td:
            out_path = os.path.join(td, "test.ass")
            cues = [
                {"start": 1.0, "end": 9.0, "text": "Before clip should be skipped"},
                {"start": 10.0, "end": 14.5, "text": "Are you afraid {of} death?\nNo."},
                {"start": 15.0, "end": 22.0, "text": "Machines do not feel."},
            ]
            result = SubtitleBuilder.generate_ass(
                cues, out_path, aspect_ratio_key="unknown_preset", time_offset=10.0, max_duration=8.0
            )
            self.assertTrue(os.path.isfile(result))
            with open(result, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("PlayResX: 1080", content)
            self.assertIn("PlayResY: 1080", content)
            self.assertNotIn("Before clip should be skipped", content)
            self.assertIn("\\{of\\}", content)
            self.assertIn("?\\NNo.", content)
            self.assertIn("Dialogue: 0,0:00:00.00,0:00:04.50", content)
            self.assertIn("Dialogue: 0,0:00:05.00,0:00:08.00", content)

    def test_generate_anidoc_ass_kinetic(self):
        with tempfile.TemporaryDirectory() as td:
            out_path = os.path.join(td, "anidoc_test.ass")
            words = [
                {"w": "TREVOR", "s": 0.5, "e": 1.0},
                {"w": "IS", "s": 1.0, "e": 1.3},
                {"w": "UNHINGED", "s": 1.3, "e": 2.2},
            ]
            result = SubtitleBuilder.generate_anidoc_ass(
                words=words,
                output_path=out_path,
                aspect_ratio_key="vertical_letterbox",
                max_duration=10.0,
                top_question="WHY IS TREVOR SO UNHINGED?",
            )
            self.assertTrue(os.path.isfile(result))
            with open(result, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("PlayResX: 1080", content)
            self.assertIn("PlayResY: 1920", content)
            self.assertIn("Style: Cap,Montserrat ExtraBold,88", content)
            self.assertIn("\\pos(540,1410)", content)
            self.assertIn("HeaderQuestion", content)
            self.assertIn("WHY IS TREVOR", content)
            self.assertIn("SO UNHINGED?", content)
            # Verify dual-layer bloom glow
            self.assertIn("\\bord18\\blur16", content)
            self.assertIn("\\bord4\\blur3", content)
            # Verify pop-in animation tag
            self.assertIn("\\fscx106\\fscy106\\t(0,90,\\fscx100\\fscy100)", content)
            # Verify karaoke dim/white colors
            self.assertIn("\\1c&H00FFFFFF&", content)
            self.assertIn("\\1c&H00A0A0A0&", content)


if __name__ == "__main__":
    unittest.main()
