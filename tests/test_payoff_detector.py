import unittest
from core.payoff_detector import ActualPayoffDetector


class TestActualPayoffDetector(unittest.TestCase):
    def test_calculate_chapter_payoff_window_long_chapter(self):
        # In a 272-second chapter (e.g. 5964 to 6236)
        # Payoff window must be reverse-sliced from chapter resolution, NOT from the start!
        window = ActualPayoffDetector.calculate_chapter_payoff_window(
            chapter_start=5964.0,
            chapter_end=6236.0,
            target_duration=55.0,
        )
        self.assertEqual(window["end"], 6235.0)
        self.assertEqual(window["start"], 6180.0)
        self.assertEqual(window["duration"], 55.0)
        self.assertEqual(window["arc_phase"], "climactic_resolution_zone")
        # Ensure it does NOT start at 5964 (the conversational exposition)
        self.assertGreater(window["start"], 6000.0)

    def test_calculate_chapter_payoff_window_short_chapter(self):
        # In a short chapter under 55s
        window = ActualPayoffDetector.calculate_chapter_payoff_window(
            chapter_start=100.0,
            chapter_end=140.0,
            target_duration=55.0,
        )
        self.assertEqual(window["start"], 100.0)
        self.assertEqual(window["end"], 140.0)
        self.assertEqual(window["duration"], 40.0)

    def test_align_window_from_climax(self):
        # A gunshot or decision occurs at 6220.0s
        window = ActualPayoffDetector.align_window_from_climax(
            climax_timestamp=6220.0,
            target_duration=55.0,
            aftermath_hold=2.0,
        )
        self.assertEqual(window["end"], 6222.0)
        self.assertEqual(window["start"], 6167.0)
        self.assertEqual(window["duration"], 55.0)
        self.assertEqual(window["climax_at"], 6220.0)


if __name__ == "__main__":
    unittest.main()
