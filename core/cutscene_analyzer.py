"""
Cutscene Dialogue & Tension Analyzer.
Identifies viral dramatic moments, emotional character confrontations, and philosophical
debates in game walkthroughs for high-retention YouTube Shorts.
"""
import re
from typing import List, Dict, Any
from config.settings import DRAMATIC_KEYWORDS


class CutsceneAnalyzer:
    """Analyzes gameplay transcript cues to extract the most engaging 30-60s Short clips."""

    def __init__(self, keywords: List[str] = DRAMATIC_KEYWORDS):
        self.keywords = [k.lower() for k in keywords]

    def score_text(self, text: str) -> float:
        """
        Computes emotional/dramatic intensity score for a line of dialogue.
        """
        score = 0.0
        lower = text.lower()

        # Keyword matching
        for kw in self.keywords:
            if kw in lower:
                score += 3.5

        # Punctuation indicators of tension and conflict
        if "?" in text:
            score += 1.5
        if "!" in text:
            score += 2.0
        if "..." in text:
            score += 1.0

        # Word count bonus (dialogue presence vs silence)
        word_count = len(re.findall(r"\w+", text))
        if 5 <= word_count <= 25:
            score += 1.0

        return score

    def find_viral_segments(
        self,
        cues: List[Dict[str, Any]],
        target_duration: int = 55,
        min_duration: int = 25,
        max_duration: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Scans cues with a sliding window to identify top cutscene segments.
        Returns ranked list of segment dicts with start, end, duration, score, and summary.
        """
        if not cues:
            return []

        segments = []
        n = len(cues)

        for i in range(n):
            start_time = cues[i]["start"]
            current_cues = []
            accumulated_score = 0.0

            for j in range(i, n):
                cue = cues[j]
                dur = cue["end"] - start_time

                if dur > max_duration:
                    break

                current_cues.append(cue)
                accumulated_score += self.score_text(cue["text"])

                if dur >= min_duration:
                    density = accumulated_score / max(1.0, dur / 30.0)
                    segments.append({
                        "start": round(start_time, 2),
                        "end": round(cue["end"], 2),
                        "duration": round(dur, 2),
                        "score": round(density, 2),
                        "dialogue_count": len(current_cues),
                        "sample_dialogue": " | ".join(c["text"] for c in current_cues[:4]),
                    })

        if not segments:
            # Fallback to first available window if no cues met threshold
            first_start = cues[0]["start"]
            fallback_end = min(first_start + target_duration, cues[-1]["end"])
            return [{
                "start": round(first_start, 2),
                "end": round(fallback_end, 2),
                "duration": round(fallback_end - first_start, 2),
                "score": 10.0,
                "dialogue_count": len(cues),
                "sample_dialogue": cues[0]["text"],
            }]

        # Sort by score descending
        segments.sort(key=lambda x: x["score"], reverse=True)

        # Deduplicate overlapping segments (keep non-overlapping top picks)
        non_overlapping = []
        for cand in segments:
            overlap = False
            for picked in non_overlapping:
                # If overlap is > 15s, skip
                latest_start = max(cand["start"], picked["start"])
                earliest_end = min(cand["end"], picked["end"])
                if (earliest_end - latest_start) > 15:
                    overlap = True
                    break
            if not overlap:
                non_overlapping.append(cand)
            if len(non_overlapping) >= 5:
                break

        return non_overlapping

    @staticmethod
    def generate_short_title(game_name: str, key_phrase: str) -> str:
        """
        Creates an engaging, click-worthy title formatted like viral game cutscenes.
        Example: "Connor: Just a Machine or Living Being? | Detroit: Become Human"
        """
        clean_phrase = key_phrase.strip().strip(".!?,")
        if len(clean_phrase) > 55:
            clean_phrase = clean_phrase[:52] + "..."

        if game_name:
            return f"{clean_phrase} | {game_name}"
        return clean_phrase
