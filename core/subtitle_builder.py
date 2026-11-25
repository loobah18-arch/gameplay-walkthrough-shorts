"""
ASS Subtitle Builder for High-Retention YouTube Shorts.
Supports 1:1 Square (1080x1080) and 9:16 Vertical (1080x1920) layouts with keyword highlights.
"""
import os
import re
from typing import List, Dict, Any, Optional
from config.settings import SUBTITLE_STYLE, DRAMATIC_KEYWORDS, ASPECT_RATIOS


class SubtitleBuilder:
    """Builds styled ASS subtitle files from cue lists."""

    @staticmethod
    def format_ass_time(seconds: float) -> str:
        """Converts float seconds into ASS timestamp format: H:MM:SS.cc"""
        total_cs = int(round(max(0.0, float(seconds)) * 100))
        h, rem = divmod(total_cs, 360000)
        m, rem = divmod(rem, 6000)
        s, cs = divmod(rem, 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @staticmethod
    def _escape_ass_text(text: str) -> str:
        """Escapes braces and normalizes line breaks for safe ASS Dialogue lines."""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        # Escape backslashes/braces so raw subtitle braces are not parsed as override tags
        normalized = normalized.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        return normalized.replace("\n", "\\N")

    @classmethod
    def highlight_text(cls, text: str, keywords: List[str] = DRAMATIC_KEYWORDS) -> str:
        """
        Wraps matched emotional/dramatic words or multi-word phrases in ASS color tags.
        Preserves CinematicDefault Bold=1 styling after highlighted spans.
        """
        safe_text = cls._escape_ass_text(text)
        if not safe_text or not keywords:
            return safe_text

        highlight_color = SUBTITLE_STYLE["highlight_color"]
        primary_color = SUBTITLE_STYLE["primary_color"]

        cleaned_kws = sorted({k.strip() for k in keywords if k and k.strip()}, key=len, reverse=True)
        if not cleaned_kws:
            return safe_text

        pattern = re.compile(
            r"(?<!\w)(" + "|".join(re.escape(k) for k in cleaned_kws) + r")(?!\w)",
            re.IGNORECASE,
        )

        # Avoid matching inside existing \N newline escapes by protecting \N
        parts = safe_text.split("\\N")
        highlighted_parts = []
        for part in parts:
            highlighted_parts.append(
                pattern.sub(
                    lambda m: f"{{\\c{highlight_color}\\b1}}{m.group(0)}{{\\c{primary_color}\\b1}}",
                    part,
                )
            )
        return "\\N".join(highlighted_parts)

    @classmethod
    def format_header_question(cls, question: str) -> str:
        """
        Formats clear, concise, and engaging question hooks matching reference style xoJydV-xKVw:
        All-caps, clean white with provocative debate words in punchy crimson red or gold.
        Strips verbose location premises (e.g. 'FOO AT CLIFF | ' -> 'DID DEVIN WESTON DESERVE THIS ENDING?').
        """
        cleaned = cls._escape_ass_text(question).strip().upper()
        # If a pipe premise exists, extract the punchy question part
        if "|" in cleaned:
            parts = cleaned.split("|", 1)
            cleaned = parts[1].strip() if ("?" in parts[1] or len(parts[1].strip()) > 5) else parts[0].strip()

        # Accent highlight color (vibrant red &H002020FF& or gold &H0000D4FF&)
        hl = SUBTITLE_STYLE.get("accent_color", "&H002020FF&")
        white = "&H00FFFFFF&"

        # Highlight key dramatic words
        keywords = [
            "DESERVE", "ENDING", "1V1", "BEAT", "COLDEST", "SURVIVE",
            "KILL", "CHOICE", "BETRAYAL", "VILLAIN", "REDEMPTION",
            "DEVIANT", "SACRIFICE", "MACHINE", "TRUTH", "CANON",
            "MONSTER", "EVIL", "WRONG", "RIGHT", "FORGIVE", "DEAD"
        ]

        pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b", re.IGNORECASE)
        if pattern.search(cleaned):
            styled = pattern.sub(lambda m: f"{{\\c{hl}\\b1}}{m.group(0)}{{\\c{white}\\b1}}", cleaned)
            return f"{{\\b1\\c{white}}}{styled}"

        # If no specific keyword matched, highlight the last 1-2 words
        words = cleaned.split()
        if len(words) > 3:
            lead = " ".join(words[:-2])
            tail = " ".join(words[-2:])
            return f"{{\\b1\\c{white}}}{lead} {{\\c{hl}\\b1}}{tail}"

        return f"{{\\b1\\c{white}}}{cleaned}"

    @classmethod
    def generate_ass(
        cls,
        cues: List[Dict[str, Any]],
        output_path: str,
        aspect_ratio_key: str = "square",
        time_offset: float = 0.0,
        max_duration: Optional[float] = None,
        top_question: Optional[str] = None,
    ) -> str:
        """
        Generates a complete ASS subtitle file with optional AniDoc top engaging question.
        `time_offset`: subtracts start_time of clip so subtitle timing starts at 0.0s.
        `max_duration`: optional clip duration ceiling so trailing cues don't overflow.
        `top_question`: optional engaging question placed at the top (safe-zone header).
        """
        if aspect_ratio_key not in ASPECT_RATIOS:
            aspect_ratio_key = "square"

        preset = ASPECT_RATIOS[aspect_ratio_key]
        res_x = preset["play_res_x"]
        res_y = preset["play_res_y"]

        is_square = "square" in aspect_ratio_key
        font_size = (
            SUBTITLE_STYLE["font_size_square"]
            if is_square
            else SUBTITLE_STYLE["font_size_vertical"]
        )
        margin_v = (
            SUBTITLE_STYLE["margin_v_square"]
            if is_square
            else SUBTITLE_STYLE["margin_v_vertical"]
        )

        if aspect_ratio_key == "vertical_letterbox":
            # 1080x1920 canvas with 16:9 cutscene centered (y=656 to 1264).
            # Top black bar is 656px tall (y=0 to 656).
            # MarginV=280 places the question centered in the top black space, safely off scenes.
            header_font_size = 52
            header_margin_v = 280
        elif aspect_ratio_key == "square_letterbox":
            # 1080x1920 canvas with 1:1 square cutscene centered (y=420 to 1500).
            # Top black bar is 420px tall (y=0 to 420).
            # MarginV=180 places the question centered in the top black space, safely off scenes.
            header_font_size = 48
            header_margin_v = 180
        elif is_square:
            header_font_size = 36
            header_margin_v = 45
        else:
            header_font_size = 44
            header_margin_v = 140

        header = f"""[Script Info]
Title: Cinematic Walkthrough Short Subtitles
ScriptType: v4.00+
WrapStyle: 1
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {res_x}
PlayResY: {res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CinematicDefault,{SUBTITLE_STYLE['font_name']},{font_size},{SUBTITLE_STYLE['primary_color']},&H000000FF,{SUBTITLE_STYLE['outline_color']},{SUBTITLE_STYLE['outline_color']},1,0,0,0,100,100,0.5,0,1,{SUBTITLE_STYLE['outline_width']},{SUBTITLE_STYLE['shadow_depth']},2,40,40,{margin_v},1
Style: HeaderQuestion,{SUBTITLE_STYLE['font_name']},{header_font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0.8,0,1,0,0,8,60,60,{header_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []
        clip_end_sec = max_duration if max_duration is not None else 58.0
        if top_question and top_question.strip():
            styled_q = cls.format_header_question(top_question)
            end_q_str = cls.format_ass_time(clip_end_sec)
            events.append(f"Dialogue: 1,0:00:00.00,{end_q_str},HeaderQuestion,,0,0,0,,{styled_q}")

        for cue in cues:
            rel_start = cue["start"] - time_offset
            rel_end = cue["end"] - time_offset

            # Skip cues that end completely before the clip starts
            if rel_end <= 0.0:
                continue
            if max_duration is not None and rel_start >= max_duration:
                continue

            start_sec = max(0.0, rel_start)
            end_sec = rel_end if max_duration is None else min(rel_end, max_duration)
            if end_sec <= start_sec:
                end_sec = start_sec + 0.5
                if max_duration is not None:
                    end_sec = min(end_sec, max_duration)

            start_str = cls.format_ass_time(start_sec)
            end_str = cls.format_ass_time(end_sec)
            styled_text = cls.highlight_text(cue["text"])
            if not styled_text:
                continue

            events.append(f"Dialogue: 0,{start_str},{end_str},CinematicDefault,,0,0,0,,{styled_text}")

        full_content = header + "\n".join(events) + "\n"

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        return output_path
