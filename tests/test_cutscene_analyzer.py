import unittest
from core.cutscene_analyzer import CutsceneAnalyzer


class TestCutsceneAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = CutsceneAnalyzer()

    def test_score_text(self):
        score_high = self.analyzer.score_text("Connor is just a machine, not a living being! Are you afraid of death?")
        score_low = self.analyzer.score_text("The car is over there.")
        self.assertGreater(score_high, score_low)
        self.assertGreaterEqual(score_high, 7.0)

    def test_check_incomplete_ending(self):
        # Incomplete sentence endings should return True
        self.assertTrue(self.analyzer.check_incomplete_ending("and then he went to the"))
        self.assertTrue(self.analyzer.check_incomplete_ending("because if we don't"))
        self.assertTrue(self.analyzer.check_incomplete_ending("Wait, but..."))
        self.assertTrue(self.analyzer.check_incomplete_ending("I have to tell you,"))
        self.assertTrue(self.analyzer.check_incomplete_ending("He was going to"))
        self.assertTrue(self.analyzer.check_incomplete_ending(""))

        # Complete and definitive endings should return False
        self.assertFalse(self.analyzer.check_incomplete_ending("That is my purpose."))
        self.assertFalse(self.analyzer.check_incomplete_ending("I made my choice!"))
        self.assertFalse(self.analyzer.check_incomplete_ending("Drop your weapon."))
        self.assertFalse(self.analyzer.check_incomplete_ending("Are you afraid of death?"))

    def test_score_payoff_mic_drop(self):
        cue = {"start": 50.0, "end": 55.0, "text": "I obey orders. That is my purpose."}
        next_cue = {"start": 57.0, "end": 60.0, "text": "A new scene begins."}
        payoff = self.analyzer.score_payoff(cue, next_cue=next_cue)

        self.assertTrue(payoff["has_payoff"])
        self.assertEqual(payoff["payoff_type"], "mic_drop")
        self.assertEqual(payoff["matched_keyword"], "that is my purpose")
        self.assertGreaterEqual(payoff["score"], 8.0)
        self.assertFalse(payoff["is_incomplete"])

    def test_score_payoff_decision_climax(self):
        cue = {"start": 40.0, "end": 44.0, "text": "I won't pull the trigger. I refuse!"}
        next_cue = {"start": 46.5, "end": 50.0, "text": "Hank smiles."}
        payoff = self.analyzer.score_payoff(cue, next_cue=next_cue)

        self.assertTrue(payoff["has_payoff"])
        self.assertEqual(payoff["payoff_type"], "decision_or_climax")
        self.assertGreaterEqual(payoff["score"], 7.5)

    def test_score_payoff_revelation(self):
        cue = {"start": 30.0, "end": 34.0, "text": "The truth is, I lied to you."}
        next_cue = {"start": 36.0, "end": 40.0, "text": "Silence."}
        payoff = self.analyzer.score_payoff(cue, next_cue=next_cue)

        self.assertTrue(payoff["has_payoff"])
        self.assertEqual(payoff["payoff_type"], "revelation_or_truth")

    def test_score_payoff_incomplete_rejected(self):
        cue = {"start": 20.0, "end": 24.0, "text": "We need to go right now because"}
        next_cue = {"start": 24.1, "end": 26.0, "text": "it is too dangerous."}
        payoff = self.analyzer.score_payoff(cue, next_cue=next_cue)

        self.assertFalse(payoff["has_payoff"])
        self.assertTrue(payoff["is_incomplete"])

    def test_score_payoff_mid_sentence_split(self):
        cue = {"start": 10.0, "end": 12.0, "text": "He took the car"}
        next_cue = {"start": 12.1, "end": 14.0, "text": "and drove into town."}
        payoff = self.analyzer.score_payoff(cue, next_cue=next_cue)

        self.assertFalse(payoff["has_payoff"])
        self.assertTrue(payoff["is_incomplete"])
        self.assertEqual(payoff["payoff_type"], "mid_sentence_split")

    def test_score_hook(self):
        hook_question = self.analyzer.score_hook({"text": "Are you afraid of death?"})
        hook_statement = self.analyzer.score_hook({"text": "The weather is cloudy today."})
        self.assertGreater(hook_question, hook_statement)
        self.assertGreaterEqual(hook_question, 5.0)

    def test_find_viral_segments_requires_payoff(self):
        cues = [
            {"start": 10.0, "end": 15.0, "text": "Are you afraid of death?"},
            {"start": 15.0, "end": 22.0, "text": "Machines don't have emotions."},
            {"start": 22.0, "end": 35.0, "text": "I feel alive. I don't want to die!"},
            {"start": 35.0, "end": 42.0, "text": "You have to choose and"},  # Incomplete ending
            {"start": 42.0, "end": 50.0, "text": "That is my purpose."},     # Proper payoff (mic drop)
        ]

        # With require_payoff=True
        segments = self.analyzer.find_viral_segments(cues, min_duration=25, max_duration=60, require_payoff=True)
        self.assertGreater(len(segments), 0)

        # Every selected segment must end with a valid payoff
        for seg in segments:
            self.assertTrue(seg["has_proper_payoff"])
            self.assertIn(seg["payoff_type"], ["mic_drop", "decision_or_climax", "revelation_or_truth", "definitive_closure"])
            self.assertFalse(seg["closing_dialogue"].endswith("and"))

    def test_generate_short_title(self):
        title = CutsceneAnalyzer.generate_short_title(
            "Detroit: Become Human",
            "Connor Is Just a Machine",
            payoff_phrase="That Is My Purpose"
        )
        self.assertIn("Detroit: Become Human", title)
        self.assertIn("That Is My Purpose", title)


if __name__ == "__main__":
    unittest.main()
