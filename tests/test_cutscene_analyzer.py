import unittest
from core.cutscene_analyzer import CutsceneAnalyzer


class TestCutsceneAnalyzer(unittest.TestCase):
    def test_score_text(self):
        analyzer = CutsceneAnalyzer()
        score_high = analyzer.score_text("Connor is just a machine, not a living being! Are you afraid of death?")
        score_low = analyzer.score_text("The car is over there.")
        self.assertGreater(score_high, score_low)
        self.assertGreaterEqual(score_high, 7.0)

    def test_find_viral_segments(self):
        analyzer = CutsceneAnalyzer()
        cues = [
            {"start": 10.0, "end": 15.0, "text": "Are you afraid of death?"},
            {"start": 15.0, "end": 22.0, "text": "Machines don't have emotions."},
            {"start": 22.0, "end": 35.0, "text": "I feel alive. I don't want to die!"},
            {"start": 35.0, "end": 48.0, "text": "You are a deviant, you have a choice."},
            {"start": 48.0, "end": 65.0, "text": "I obey orders. That is my purpose."},
        ]
        segments = analyzer.find_viral_segments(cues, min_duration=25, max_duration=60)
        self.assertGreater(len(segments), 0)
        top = segments[0]
        self.assertGreaterEqual(top["duration"], 25)
        self.assertGreater(top["score"], 0)

    def test_generate_short_title(self):
        title = CutsceneAnalyzer.generate_short_title("Detroit: Become Human", "Connor Is Just a Machine, Not a Living Being")
        self.assertIn("Connor Is Just a Machine", title)
        self.assertIn("Detroit: Become Human", title)


if __name__ == "__main__":
    unittest.main()
