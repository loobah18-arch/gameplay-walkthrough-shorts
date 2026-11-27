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
        self.unfinished_trails = {
            w.lower() for w in (unfinished_trails or UNFINISHED_SENTENCE_TRAILS)
        }

    @staticmethod
    def _contains_phrase(text_lower: str, phrase: str) -> bool:
        """Matches keyword/phrase on word boundaries so substrings inside words never match."""
        return bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text_lower))

    @staticmethod
    def _strip_sound_tags(text: str) -> str:
        """Removes non-speech caption markers like [Music] or [Applause]."""
        return re.sub(r"\[[^\]]+\]", " ", text or "").strip()

    def check_incomplete_ending(self, text: str) -> bool:
        """
        Determines whether a sentence or subtitle cue ends prematurely,
        e.g. dangling conjunctions, trailing prepositions, trailing commas/ellipses.
        """
        cleaned = self._strip_sound_tags(text)
        if not cleaned:
            return True

        # Check trailing incomplete punctuation: commas, colons, semicolons, dashes, trailing ellipses
        if cleaned.endswith((",", ":", ";", "-", "—", "...", "…")):
            return True

        # Strip ending quotes or brackets for word-level inspection
        stripped = re.sub(r'["\'”’\)\]]+$', "", cleaned).rstrip()

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

        # If text lacks terminal punctuation (. ! ?), auxiliary verbs and pronouns indicate an incomplete clause
        has_terminal_punct = bool(re.search(r'[.!?]["\'”’\)\]]*$', cleaned))
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

        if "?" in text:
            score += 3.5

        if "!" in text:
            score += 2.0

        for kw in self.keywords:
            if self._contains_phrase(lower, kw):
                score += 3.0
                break

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
        text = self._strip_sound_tags(cue.get("text", ""))
        result: Dict[str, Any] = {
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
            if pause_duration < 0.35:
                next_words = next_cue.get("text", "").strip().split()
                if next_words:
                    head = next_words[0].lstrip("\"'(-[“‘")
                    if (head and head[0].islower()) or head.lower() in self.unfinished_trails:
                        result["is_incomplete"] = True
                        result["payoff_type"] = "mid_sentence_split"
                        return result
        result["pause_after"] = round(pause_duration, 2)

        # 3. Word-boundary keyword payoff classification
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
                if self._contains_phrase(lower, kw):
                    matched_category = cat
                    matched_kw = kw
                    base_score = category_weights.get(cat, 6.0)
                    break
            if matched_category:
                break

        # 4. Terminal punctuation (handling trailing quotes/parens)
        punct_match = re.search(r'([.!?])["\'”’\)\]]*$', text)
        terminal_punct = punct_match.group(1) if punct_match else ""
        if terminal_punct == "!":
            base_score += 2.5
        elif terminal_punct == ".":
            base_score += 2.0
        elif terminal_punct == "?":
            base_score += 1.5

        # 5. Dramatic beat / lingering silence bonus
        if pause_duration >= 1.5:
            base_score += 3.5
        elif pause_duration >= 0.8:
            base_score += 2.0
        elif pause_duration < 0.4 and next_cue:
            base_score -= 1.0

        # 6. Evaluation threshold
        word_count = len(re.findall(r"\b[a-zA-Z']+\b", text))
        if matched_category:
            result["has_payoff"] = True
            result["score"] = round(base_score, 2)
            result["payoff_type"] = matched_category
            result["matched_keyword"] = matched_kw
        elif base_score >= 4.0 and bool(terminal_punct):
            result["has_payoff"] = True
            result["score"] = round(base_score, 2)
            result["payoff_type"] = "definitive_closure"
        elif not terminal_punct and pause_duration >= 1.5 and word_count >= 3 and (
            self.score_text(text) >= 1.5 or pause_duration >= 2.0
        ):
            # Support unpunctuated YouTube auto-captions ending cleanly on a lingering dramatic beat
            result["has_payoff"] = True
            result["score"] = round(max(4.0, base_score + 0.5), 2)
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

        for kw in self.keywords:
            if self._contains_phrase(lower, kw):
                score += 3.5

        if "?" in text:
            score += 1.5
        if "!" in text:
            score += 2.0
        if "..." in text:
            score += 1.0

        word_count = len(re.findall(r"\w+", text))
        if 5 <= word_count <= 25:
            score += 1.0

        return score

    GAMEPLAY_BLACKLIST_KEYWORDS = [
        "gameplay", "free roam", "freeroam", "roaming", "exploration", "side quest",
        "looting", "driving around", "traversal", "inventory", "open world",
        "collectible", "easter egg", "tutorial", "practice",
    ]

    CUTSCENE_WHITELIST_KEYWORDS = [
        "cutscene", "cinematic", "ending", "story", "confrontation", "interrogation",
        "decision", "choice", "climax", "final", "meeting", "face off", "standoff",
        "dialogue", "conversation", "boss", "reveal", "truth", "death",
    ]

    @classmethod
    def score_chapter_cutscene_affinity(cls, title: str) -> float:
        """
        Scores chapter title: heavily rewards cinematic cutscene markers and
        heavily penalizes/discards pure gameplay, free roam, and traversal.
        """
        if not title:
            return 0.0
        lower = title.lower()
        for bad in cls.GAMEPLAY_BLACKLIST_KEYWORDS:
            if bad in lower:
                return -100.0  # Hard reject

        score = 0.0
        for good in cls.CUTSCENE_WHITELIST_KEYWORDS:
            if good in lower:
                score += 15.0
        return score

    def find_viral_segments(
        self,
        cues: List[Dict[str, Any]],
        target_duration: int = 55,
        min_duration: int = 25,
        max_duration: int = 60,
        require_payoff: bool = True,
        min_payoff_score: float = 4.0,
        min_dialogue_lines: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Scans cues with a sliding window to identify top cutscene segments.
        Filters out sparse gameplay stretches (requires min_dialogue_lines).
        When require_payoff=True, strictly filters out candidates lacking a definitive climax,
        punchline, or moral choice, and returns [] if none meet the threshold.
        """
        if not cues:
            return []

        if min_duration > max_duration:
            min_duration = max_duration

        segments = []
        n = len(cues)

        for i in range(n):
            if not self._strip_sound_tags(cues[i].get("text", "")):
                continue
            start_time = cues[i]["start"]
            hook_score = self.score_hook(cues[i])
            current_cues = []
            accumulated_body_score = 0.0

            for j in range(i, n):
                cue = cues[j]
                dur = cue["end"] - start_time

                if dur > max_duration:
                    break

                speech_text = self._strip_sound_tags(cue.get("text", ""))
                if not speech_text:
                    continue

                current_cues.append(cue)
                accumulated_body_score += self.score_text(speech_text)

                if dur >= min_duration:
                    if len(current_cues) < min_dialogue_lines:
                        # Exclude sparse gameplay sections with isolated grunts or words
                        continue

                    next_cue = cues[j + 1] if (j + 1 < n) else None
                    payoff = self.score_payoff(cue, next_cue=next_cue)

                    if require_payoff:
                        if not payoff["has_payoff"] or payoff["is_incomplete"] or payoff["score"] < min_payoff_score:
                            continue

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
            if require_payoff:
                # Never silently bypass strict payoff enforcement
                return []

            first_start = cues[0]["start"]
            capped_target = min(target_duration, max_duration)
            fallback_end = min(first_start + capped_target, cues[-1]["end"])
            return [{
                "start": round(first_start, 2),
                "end": round(fallback_end, 2),
                "duration": round(max(0.0, fallback_end - first_start), 2),
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

        segments.sort(key=lambda x: x["score"], reverse=True)

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
        """
        phrase = payoff_phrase if (payoff_phrase and len(payoff_phrase) >= 10) else key_phrase
        clean_phrase = phrase.strip().strip(".!?,\"'")
        if len(clean_phrase) > 55:
            clean_phrase = clean_phrase[:52] + "..."

        if game_name:
            return f"{clean_phrase} | {game_name}"
        return clean_phrase
