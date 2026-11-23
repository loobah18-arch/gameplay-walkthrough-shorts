"""
Cutscene Dialogue & Tension Analyzer.
Identifies viral dramatic moments, emotional character confrontations, and philosophical
debates in game walkthroughs for high-retention YouTube Shorts with strict narrative payoff.
"""
import re
from typing import List, Dict, Any, Optional
from config.settings import DRAMATIC_KEYWORDS, PAYOFF_KEYWORDS, UNFINISHED_SENTENCE_TRAILS


class CutsceneAnalyzer:
    """Analyzes gameplay transcript cues to extract high-retention Short clips with decisive payoffs."""

    def __init__(
        self,
        keywords: Optional[List[str]] = None,
        payoff_keywords: Optional[Dict[str, List[str]]] = None,
        unfinished_trails: Optional[List[str]] = None,
    ):
        self.keywords = [k.lower() for k in (keywords or DRAMATIC_KEYWORDS)]
        self.payoff_keywords = payoff_keywords or PAYOFF_KEYWORDS
        self.unfinished_trails = set(
            w.lower() for w in (unfinished_trails or UNFINISHED_SENTENCE_TRAILS)
        )

    def check_incomplete_ending(self, text: str) -> bool:
        """
        Determines whether a sentence or subtitle cue ends prematurely,
        e.g. dangling conjunctions, trailing prepositions, trailing commas/ellipses.
        """
        if not text:
            return True

        cleaned = text.strip()
        if not cleaned:
            return True

        # Check trailing incomplete punctuation: commas, colons, semicolons, dashes, trailing ellipses
        if cleaned.endswith((",", ":", ";", "-", "—", "...", "…")):
            return True

        # Strip ending quotes or brackets for word-level inspection
        stripped = re.sub(r'["\'\)\]\}]+$', '', cleaned).rstrip()

        # Find words
        words = re.findall(r"\b[a-zA-Z']+\b", stripped.lower())
        if not words:
            return True

        last_word = words[-1]
        if last_word in self.unfinished_trails:
            return True

        # Multi-word trailing phrases
        if len(words) >= 2:
            two_word_tail = f"{words[-2]} {words[-1]}"
            if two_word_tail in {"going to", "want to", "as if", "such as", "kind of", "sort of", "out of"}:
                return True

        # If text lacks any terminal punctuation (. ! ?), auxiliary verbs and dangling pronouns indicate an incomplete clause
        has_terminal_punct = bool(re.search(r'[.!?]["\'”’]?$', cleaned))
        if not has_terminal_punct:
            if last_word in {
                "don't", "didn't", "can't", "won't", "couldn't", "wouldn't", "shouldn't",
                "is", "are", "was", "were", "be", "been", "have", "has", "had",
                "do", "does", "did", "will", "would", "can", "could", "should",
                "i", "you", "he", "she", "it", "we", "they", "we're", "you're", "they're",
            }:
                return True

        return False

    def score_hook(self, cue: Dict[str, Any]) -> float:
        """
        Evaluates the opening line of a candidate Short for hook potential.
        Questions, high tension keywords, or exclamations earn bonus points.
        """
        text = cue.get("text", "").strip()
        if not text:
            return 0.0

        score = 0.0
        lower = text.lower()

        # Questions create powerful curiosity loops
        if "?" in text:
            score += 3.5

        # Exclamations create immediate urgency
        if "!" in text:
            score += 2.0

        # Dramatic keywords in the hook
        for kw in self.keywords:
            if kw in lower:
                score += 3.0
                break

        # Dialogue density / length
        word_count = len(re.findall(r"\w+", text))
        if 4 <= word_count <= 20:
            score += 1.5

        return score

    def score_payoff(
        self,
        cue: Dict[str, Any],
        next_cue: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates whether a cue delivers a satisfying narrative payoff:
        - Mic drop (iconic one-liner)
        - Decision / Climax (moral choice, life-or-death action)
        - Revelation (truth or secret revealed)
        - Definitive closure (clean terminal punctuation followed by dramatic pause)

        Rejects unfinished sentences, mid-clause cuts, or trailing conjunctions.
        """
        text = cue.get("text", "").strip()
        result = {
            "has_payoff": False,
            "score": 0.0,
            "payoff_type": "none",
            "is_incomplete": False,
            "matched_keyword": None,
            "pause_after": 0.0,
            "line": text,
        }

        if not text:
            result["is_incomplete"] = True
            return result

        # 1. Reject syntactically incomplete endings
        if self.check_incomplete_ending(text):
            result["is_incomplete"] = True
            result["payoff_type"] = "incomplete"
            return result

        # 2. Check silence gap after the cue
        pause_duration = 3.0
        if next_cue:
            pause_duration = max(0.0, next_cue["start"] - cue["end"])
            # If the pause is almost zero and next cue starts lowercase, it's mid-sentence subtitle chunking
            if pause_duration < 0.35:
                next_words = next_cue.get("text", "").strip().split()
                if next_words and (next_words[0][0].islower() or next_words[0].lower() in self.unfinished_trails):
                    result["is_incomplete"] = True
                    result["payoff_type"] = "mid_sentence_split"
                    return result
        result["pause_after"] = round(pause_duration, 2)

        # 3. Keyword-based payoff classification
        lower = text.lower()
        base_score = 0.0
        matched_category = None
        matched_kw = None

        category_weights = {
            "mic_drop": 8.0,
            "decision_or_climax": 7.5,
            "revelation_or_truth": 7.0,
        }

        for cat, kws in self.payoff_keywords.items():
            for kw in kws:
                if kw in lower:
                    matched_category = cat
                    matched_kw = kw
                    base_score = category_weights.get(cat, 6.0)
                    break
            if matched_category:
                break

        # 4. Terminal punctuation and conclusive phrasing bonus
        if text.endswith("!"):
            base_score += 2.5
        elif text.endswith("."):
            base_score += 2.0
        elif text.endswith("?"):
            base_score += 1.5

        # 5. Dramatic beat / lingering silence bonus
        if pause_duration >= 1.5:
            base_score += 3.5  # Scene transition or cinematic silence
        elif pause_duration >= 0.8:
            base_score += 2.0  # Natural dramatic pause
        elif pause_duration < 0.4 and next_cue:
            base_score -= 1.0  # Fast back-and-forth

        # 6. Evaluation threshold
        # If keyword matched, or if strong conclusive line with dramatic pause (score >= 4.0)
        if matched_category:
            result["has_payoff"] = True
            result["score"] = round(base_score, 2)
            result["payoff_type"] = matched_category
            result["matched_keyword"] = matched_kw
        elif base_score >= 4.0 and (text.endswith((".", "!", "?"))):
            result["has_payoff"] = True
            result["score"] = round(base_score, 2)
            result["payoff_type"] = "definitive_closure"
        else:
            result["has_payoff"] = False
            result["score"] = round(base_score, 2)
            result["payoff_type"] = "none"

        return result

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
        require_payoff: bool = True,
        min_payoff_score: float = 4.0,
    ) -> List[Dict[str, Any]]:
        """
        Scans cues with a sliding window to identify top cutscene segments.
        When require_payoff=True, strictly filters out candidates lacking a definitive climax,
        punchline, or moral choice, and rejects incomplete mid-sentence endings.
        """
        if not cues:
            return []

        segments = []
        n = len(cues)

        for i in range(n):
            start_time = cues[i]["start"]
            hook_score = self.score_hook(cues[i])
            current_cues = []
            accumulated_body_score = 0.0

            for j in range(i, n):
                cue = cues[j]
                dur = cue["end"] - start_time

                if dur > max_duration:
                    break

                current_cues.append(cue)
                accumulated_body_score += self.score_text(cue["text"])

                if dur >= min_duration:
                    next_cue = cues[j + 1] if (j + 1 < n) else None
                    payoff = self.score_payoff(cue, next_cue=next_cue)

                    # Strict payoff filter: reject if no payoff, incomplete sentence, or weak payoff score
                    if require_payoff:
                        if not payoff["has_payoff"] or payoff["is_incomplete"] or payoff["score"] < min_payoff_score:
                            continue

                    # Composite score: Hook (25%), Dialogue Tension Density (35%), Payoff (40%)
                    density = accumulated_body_score / max(1.0, dur / 30.0)
                    composite_score = (0.25 * hook_score) + (0.35 * density) + (0.40 * payoff["score"])

                    segments.append({
                        "start": round(start_time, 2),
                        "end": round(cue["end"], 2),
                        "duration": round(dur, 2),
                        "score": round(composite_score, 2),
                        "hook_score": round(hook_score, 2),
                        "payoff_score": round(payoff["score"], 2),
                        "payoff_type": payoff["payoff_type"],
                        "payoff_line": payoff["line"],
                        "has_proper_payoff": payoff["has_payoff"],
                        "pause_after": round(payoff["pause_after"], 2),
                        "dialogue_count": len(current_cues),
                        "sample_dialogue": " | ".join(c["text"] for c in current_cues[:4]),
                        "closing_dialogue": cue["text"],
                    })

        if not segments:
            # If strict payoff eliminated all segments, try relaxed pass if require_payoff was True
            if require_payoff:
                return self.find_viral_segments(
                    cues,
                    target_duration=target_duration,
                    min_duration=min_duration,
                    max_duration=max_duration,
                    require_payoff=False,
                )

            # Fallback to first available window if no cues met threshold
            first_start = cues[0]["start"]
            fallback_end = min(first_start + target_duration, cues[-1]["end"])
            return [{
                "start": round(first_start, 2),
                "end": round(fallback_end, 2),
                "duration": round(fallback_end - first_start, 2),
                "score": 10.0,
                "hook_score": 0.0,
                "payoff_score": 0.0,
                "payoff_type": "none",
                "payoff_line": cues[-1]["text"],
                "has_proper_payoff": False,
                "pause_after": 0.0,
                "dialogue_count": len(cues),
                "sample_dialogue": cues[0]["text"],
                "closing_dialogue": cues[-1]["text"],
            }]

        # Sort by composite score descending
        segments.sort(key=lambda x: x["score"], reverse=True)

        # Deduplicate overlapping segments (keep non-overlapping top picks)
        non_overlapping = []
        for cand in segments:
            overlap = False
            for picked in non_overlapping:
                latest_start = max(cand["start"], picked["start"])
                earliest_end = min(cand["end"], picked["end"])
                if (earliest_end - latest_start) > 12:
                    overlap = True
                    break
            if not overlap:
                non_overlapping.append(cand)
            if len(non_overlapping) >= 5:
                break

        return non_overlapping

    @staticmethod
    def generate_short_title(game_name: str, key_phrase: str, payoff_phrase: Optional[str] = None) -> str:
        """
        Creates an engaging, click-worthy title formatted like viral game cutscenes.
        Incorporates payoff or key phrase.
        Example: "Connor: Just a Machine or Living Being? | Detroit: Become Human"
        """
        phrase = payoff_phrase if (payoff_phrase and len(payoff_phrase) >= 10) else key_phrase
        clean_phrase = phrase.strip().strip(".!?,")
        if len(clean_phrase) > 55:
            clean_phrase = clean_phrase[:52] + "..."

        if game_name:
            return f"{clean_phrase} | {game_name}"
        return clean_phrase
