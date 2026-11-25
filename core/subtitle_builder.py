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
    def generate_ass(
        cls,
        cues: List[Dict[str, Any]],
        output_path: str,
        aspect_ratio_key: str = "square",
        time_offset: float = 0.0,
        max_duration: Optional[float] = None,
    ) -> str:
        """
        Generates a complete ASS subtitle file.
        `time_offset`: subtracts start_time of clip so subtitle timing starts at 0.0s.
        `max_duration`: optional clip duration ceiling so trailing cues don't overflow.
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
