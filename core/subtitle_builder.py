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
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int(round((seconds - int(seconds)) * 100))
        if cs >= 100:
            cs = 99
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @classmethod
    def highlight_text(cls, text: str, keywords: List[str] = DRAMATIC_KEYWORDS) -> str:
        """
        Wraps matched emotional/dramatic keywords in ASS color override tags.
        Primary: White (&H00FFFFFF&), Highlight: Gold Amber (&H0000D4FF&)
        """
        words = text.split()
        styled_words = []
        highlight_color = SUBTITLE_STYLE["highlight_color"]
        primary_color = SUBTITLE_STYLE["primary_color"]

        lower_keywords = {k.lower() for k in keywords}

        for w in words:
            clean_word = re.sub(r"[^\w]", "", w).lower()
            if clean_word in lower_keywords:
                styled_words.append(f"{{\\c{highlight_color}\\b1}}{w}{{\\c{primary_color}\\b0}}")
            else:
                styled_words.append(w)

        return " ".join(styled_words)

    @classmethod
    def generate_ass(
        cls,
        cues: List[Dict[str, Any]],
        output_path: str,
        aspect_ratio_key: str = "square",
        time_offset: float = 0.0,
    ) -> str:
        """
        Generates a complete ASS subtitle file.
        `time_offset`: subtracts start_time of clip so subtitle timing starts at 0.0s.
        """
        preset = ASPECT_RATIOS.get(aspect_ratio_key, ASPECT_RATIOS["square"])
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

        header = f"""[Script Info]
Title: Cinematic Walkthrough Short Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {res_x}
PlayResY: {res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CinematicDefault,{SUBTITLE_STYLE['font_name']},{font_size},{SUBTITLE_STYLE['primary_color']},&H000000FF,{SUBTITLE_STYLE['outline_color']},{SUBTITLE_STYLE['outline_color']},1,0,0,0,100,100,0.5,0,1,{SUBTITLE_STYLE['outline_width']},{SUBTITLE_STYLE['shadow_depth']},2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []
        for cue in cues:
            start_sec = max(0.0, cue["start"] - time_offset)
            end_sec = max(start_sec + 0.5, cue["end"] - time_offset)

            start_str = cls.format_ass_time(start_sec)
            end_str = cls.format_ass_time(end_sec)
            styled_text = cls.highlight_text(cue["text"])

            events.append(f"Dialogue: 0,{start_str},{end_str},CinematicDefault,,0,0,0,,{styled_text}")

        full_content = header + "\n".join(events) + "\n"

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        return output_path
