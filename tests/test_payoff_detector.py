import math
import os
import struct
import tempfile
import unittest
import wave
from core.payoff_detector import ActualPayoffDetector


class TestActualPayoffDetector(unittest.TestCase):
    def test_calculate_chapter_payoff_window_long_chapter(self):
        window = ActualPayoffDetector.calculate_chapter_payoff_window(
            chapter_start=5964.0,
            chapter_end=6236.0,
            target_duration=55.0,
        )
        self.assertEqual(window["end"], 6235.0)
        self.assertEqual(window["start"], 6180.0)
        self.assertEqual(window["duration"], 55.0)
        self.assertEqual(window["arc_phase"], "climactic_resolution_zone")
        self.assertGreater(window["start"], 6000.0)

    def test_calculate_chapter_payoff_window_short_chapter(self):
        window = ActualPayoffDetector.calculate_chapter_payoff_window(
            chapter_start=100.0,
            chapter_end=140.0,
            target_duration=55.0,
        )
        self.assertEqual(window["start"], 100.0)
        self.assertEqual(window["end"], 140.0)
        self.assertEqual(window["duration"], 40.0)

    def test_chapter_and_climax_boundary_clamping(self):
        tiny = ActualPayoffDetector.calculate_chapter_payoff_window(
            chapter_start=10.0,
            chapter_end=10.5,
            target_duration=0.4,
        )
        self.assertGreaterEqual(tiny["end"], tiny["start"])
        self.assertGreaterEqual(tiny["duration"], 0.0)

        aligned = ActualPayoffDetector.align_window_from_climax(
            climax_timestamp=5.0,
            target_duration=55.0,
            min_start=10.0,
            aftermath_hold=2.0,
        )
        self.assertEqual(aligned["start"], 10.0)
        self.assertEqual(aligned["end"], 10.0)
        self.assertEqual(aligned["duration"], 0.0)

    def test_align_window_from_climax(self):
        window = ActualPayoffDetector.align_window_from_climax(
            climax_timestamp=6220.0,
            target_duration=55.0,
            aftermath_hold=2.0,
        )
        self.assertEqual(window["end"], 6222.0)
        self.assertEqual(window["start"], 6167.0)
        self.assertEqual(window["duration"], 55.0)
        self.assertEqual(window["climax_at"], 6220.0)

    def test_detect_audio_climax_on_synthetic_wav(self):
        with tempfile.TemporaryDirectory() as td:
            wav_path = os.path.join(td, "sample.wav")
            sr = 8000
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                # 1.0s loud tone followed by 1.2s silence
                frames = bytearray()
                for i in range(sr):
                    sample = int(28000 * math.sin(2 * math.pi * 440 * i / sr))
                    frames.extend(struct.pack("<h", sample))
                frames.extend(b"\x00\x00" * int(sr * 1.2))
                wf.writeframes(bytes(frames))

            events = ActualPayoffDetector.detect_audio_climax(wav_path, start_offset=100.0)
            self.assertGreater(len(events), 0)
            self.assertEqual(events[0]["type"], "climax_impact_drop")
            self.assertGreater(events[0]["timestamp"], 100.5)


if __name__ == "__main__":
    unittest.main()
