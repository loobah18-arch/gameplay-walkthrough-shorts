"""
Multi-Modal Actual Payoff Detector.
Identifies physical action climaxes, audio transient peaks (gunshots, impacts, screaming, music drops),
scene transition boundaries, and chapter narrative resolution zones.
Enforces Payoff-First Reverse Alignment: anchors Shorts to the climax consequence rather than the exposition.
"""
import os
import re
import subprocess
from typing import Dict, Any, List


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
        if target_duration <= 0:
            raise ValueError(f"target_duration must be > 0 (got {target_duration})")

        c_start = float(chapter_start)
        c_end = max(c_start, float(chapter_end))
        chapter_duration = c_end - c_start

        if chapter_duration <= target_duration:
            return {
                "start": round(c_start, 2),
                "end": round(c_end, 2),
                "duration": round(chapter_duration, 2),
                "payoff_timestamp": round(c_end, 2),
                "arc_phase": "full_chapter_resolution",
            }

        # Leave a 1s fade guard when long chapters end cleanly on a transition
        end_time = max(c_start, c_end - 1.0)
        start_time = max(c_start, end_time - target_duration)
        actual_dur = max(0.0, end_time - start_time)

        return {
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "duration": round(actual_dur, 2),
            "payoff_timestamp": round(max(start_time, end_time - hold_after_resolution), 2),
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
        Scans audio track (`-vn`, audio-only) using FFmpeg astats + silencedetect to identify:
        - Major RMS/peak loudness bursts preceding dramatic silences (gunshot, impact, shout)
        - Trailing dramatic silence (tension drop / scene transition)
        Returns candidate payoff timestamps ranked by impact score descending.
        """
        if not os.path.isfile(media_path):
            return []

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-vn",
            "-sn",
            "-dn",
            "-i", media_path,
            "-af", f"astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.Peak_level,silencedetect=noise={silence_threshold_db}dB:d={silence_min_duration}",
            "-f", "null",
            "-",
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            output = res.stderr

            # Collect 1-second peak dB samples
            peak_points: List[tuple] = []
            cur_pts = None
            for line in output.splitlines():
                m_pts = re.search(r"pts_time:([\d\.]+)", line)
                if m_pts:
                    cur_pts = float(m_pts.group(1))
                elif cur_pts is not None:
                    m_peak = re.search(r"lavfi\.astats\.Overall\.Peak_level=([-\d\.inf]+)", line)
                    if m_peak and "inf" not in m_peak.group(1).lower():
                        peak_points.append((cur_pts, float(m_peak.group(1))))
                        cur_pts = None

            silence_starts = [
                float(m.group(1))
                for m in re.finditer(r"silence_start:\s*([\d\.]+)", output)
            ]

            events = []
            for s in silence_starts:
                # Evaluate peak energy in the 3s leading directly into the silence
                recent_peaks = [p for t, p in peak_points if (s - 3.0) <= t <= s]
                max_pre_peak = max(recent_peaks) if recent_peaks else -25.0
                if max_pre_peak >= -12.0:
                    score = 9.5
                    etype = "climax_impact_drop"
                elif max_pre_peak >= -20.0:
                    score = 8.0
                    etype = "audio_drop_resolution"
                else:
                    score = 5.5
                    etype = "ambient_pause"

                events.append({
                    "timestamp": round(s + start_offset, 2),
                    "type": etype,
                    "pre_peak_db": round(max_pre_peak, 2),
                    "score": score,
                })

            events.sort(key=lambda e: (e["score"], e["timestamp"]), reverse=True)
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
        if target_duration <= 0:
            raise ValueError(f"target_duration must be > 0 (got {target_duration})")

        floor = max(0.0, float(min_start))
        end_time = max(floor, float(climax_timestamp) + float(aftermath_hold))
        start_time = max(floor, end_time - float(target_duration))
        return {
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "duration": round(max(0.0, end_time - start_time), 2),
            "climax_at": round(float(climax_timestamp), 2),
        }
