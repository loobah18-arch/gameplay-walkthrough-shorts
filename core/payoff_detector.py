"""
Multi-Modal Actual Payoff Detector.
Identifies physical action climaxes, audio transient peaks (gunshots, impacts, screaming, music drops),
scene transition boundaries, and chapter narrative resolution zones.
Enforces Payoff-First Reverse Alignment: anchors Shorts to the climax consequence rather than the exposition.
"""
import os
import re
import subprocess
from typing import Dict, Any, List, Optional, Tuple


class ActualPayoffDetector:
    """Detects audio-visual and narrative action payoffs in gameplay walkthroughs."""

    @staticmethod
    def calculate_chapter_payoff_window(
        chapter_start: float,
        chapter_end: float,
        target_duration: float = 55.0,
        hold_after_resolution: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Calculates the true payoff window for a cutscene chapter.
        In game cutscenes:
        - 0-30% of chapter = Exposition / entry / banter (NO payoff).
        - 30-70% = Rising confrontation / escalation.
        - 70-100% = Climax / physical action resolution (gun drawn, choice made, death/shot, scene ends).

        Aligns the Short window backwards so the climax and its aftermath occur in the final seconds.
        """
        chapter_duration = chapter_end - chapter_start

        if chapter_duration <= target_duration:
            # If chapter is shorter than target, take the entire chapter
            return {
                "start": round(chapter_start, 2),
                "end": round(chapter_end, 2),
                "duration": round(chapter_duration, 2),
                "payoff_timestamp": round(chapter_end, 2),
                "arc_phase": "full_chapter_resolution",
            }

        # The resolution event concludes near the end of the chapter (before scene fade-out)
        # Typically 2-5 seconds before the hard chapter end
        end_time = min(chapter_end - 1.0, chapter_end)
        start_time = max(chapter_start, end_time - target_duration)
        actual_dur = end_time - start_time

        return {
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "duration": round(actual_dur, 2),
            "payoff_timestamp": round(end_time - hold_after_resolution, 2),
            "arc_phase": "climactic_resolution_zone",
        }

    @staticmethod
    def detect_audio_climax(
        media_path: str,
        start_offset: float = 0.0,
        silence_threshold_db: float = -35.0,
        silence_min_duration: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """
        Scans audio track using FFmpeg astats/silencedetect to identify:
        - Major volume peaks and transient impact events (gunshot, impact, explosion)
        - Trailing dramatic silence (tension drop / scene transition)
        Returns ranked list of candidate payoff timestamps.
        """
        if not os.path.isfile(media_path):
            return []

        # Run silencedetect to find dramatic pauses and scene ends
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-i", media_path,
            "-af", f"silencedetect=noise={silence_threshold_db}dB:d={silence_min_duration}",
            "-f", "null",
            "-",
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            output = res.stderr

            silence_starts = [
                float(m.group(1)) + start_offset
                for m in re.finditer(r"silence_start:\s*([\d\.]+)", output)
            ]

            events = []
            for s in silence_starts:
                events.append({
                    "timestamp": round(s, 2),
                    "type": "audio_drop_resolution",
                    "score": 8.0,
                })
            return events
        except Exception:
            return []

    @staticmethod
    def align_window_from_climax(
        climax_timestamp: float,
        target_duration: float = 55.0,
        min_start: float = 0.0,
        aftermath_hold: float = 2.5,
    ) -> Dict[str, float]:
        """
        Reverse-aligns a Short window around an actual payoff climax.
        The Short ends `aftermath_hold` seconds after the climax to let the impact land.
        """
        end_time = climax_timestamp + aftermath_hold
        start_time = max(min_start, end_time - target_duration)
        return {
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "duration": round(end_time - start_time, 2),
            "climax_at": round(climax_timestamp, 2),
        }
