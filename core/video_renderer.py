"""
Video Renderer & FFmpeg Pipeline Builder.
Handles selective segment downloading via yt-dlp and builds professional filtergraphs
for 1:1 Square (Detroit Connor reference style) and 9:16 Vertical video.
"""
import os
import shutil
import subprocess
from typing import Dict, Any, List, Optional
from config.settings import (
    ASPECT_RATIOS,
    AUDIO_NORM_SETTINGS,
    VIDEO_FILTER_ENHANCE,
    OUTPUT_DIR,
    TEMP_DIR,
)
from core.cookie_manager import CookieManager


class VideoRenderer:
    """Orchestrates cloud-side FFmpeg rendering and yt-dlp section downloads."""

    def __init__(self, output_dir: str = OUTPUT_DIR, temp_dir: str = TEMP_DIR):
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

    @staticmethod
    def build_ytdlp_download_cmd(
        video_url: str,
        start_time: float,
        end_time: float,
        output_filepath: str,
        cookies_path: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> List[str]:
        """
        Builds yt-dlp command using --download-sections to download ONLY the specified cutscene window.
        Avoids downloading multi-gigabyte entire walkthrough files.
        """
        # Format section: *HH:MM:SS-HH:MM:SS
        def to_hms(s: float) -> str:
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = int(s % 60)
            return f"{h:02d}:{m:02d}:{sec:02d}"

        section = f"*{to_hms(start_time)}-{to_hms(end_time)}"
        cmd = [
            "yt-dlp",
            "--download-sections", section,
            "--force-keyframes-at-cuts",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o", output_filepath,
            "--no-playlist",
        ]
        cmd.extend(CookieManager.get_ytdlp_cookie_args(cookies_path))
        p = proxy or os.environ.get("YOUTUBE_PROXY")
        if p:
            cmd.extend(["--proxy", p])
        cmd.append(video_url)
        return cmd

    @classmethod
    def build_ffmpeg_filtergraph(
        cls,
        aspect_ratio: str = "square",
        ass_subtitle_path: Optional[str] = None,
        apply_enhancements: bool = True,
    ) -> str:
        """
        Generates FFmpeg filter_complex for:
        - 1:1 Square (crops widescreen to centered high-detail square, matching kepvkxTGqVM)
        - 9:16 Vertical Center-Crop
        - 9:16 Vertical Blurred Background
        """
        preset = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["square"])
        target_w = preset["width"]
        target_h = preset["height"]

        filters = []

        if aspect_ratio in ["square", "square_hd"]:
            # Crop 16:9 widescreen to 1:1 square centered on gameplay
            filters.append(
                f"scale=-2:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h}"
            )
        elif aspect_ratio == "vertical_crop":
            # Direct vertical 9:16 crop
            filters.append(
                f"scale=-2:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h}"
            )
        elif aspect_ratio == "vertical_blurred":
            # Blurred background + sharp centered 16:9 gameplay
            bg_filter = (
                f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},boxblur=25:5,eq=brightness=-0.08:contrast=1.05[bg]"
            )
            fg_filter = f"[0:v]scale={target_w}:-2[fg]"
            overlay_filter = f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
            sub_filter = ""
            if ass_subtitle_path and os.path.isfile(ass_subtitle_path):
                escaped_sub = ass_subtitle_path.replace(":", "\\:").replace("'", "\\'")
                sub_filter = f";[base]ass='{escaped_sub}'[v]"
            else:
                sub_filter = ";[base]copy[v]"
            return f"{bg_filter};{fg_filter};{overlay_filter}{sub_filter}"

        # Apply subtle cinematic color grading and sharpness enhancement
        if apply_enhancements:
            filters.append(VIDEO_FILTER_ENHANCE)

        # Burn ASS subtitles if provided
        if ass_subtitle_path and os.path.isfile(ass_subtitle_path):
            escaped_sub = ass_subtitle_path.replace(":", "\\:").replace("'", "\\'")
            filters.append(f"ass='{escaped_sub}'")

        return ",".join(filters)

    @classmethod
    def build_ffmpeg_render_cmd(
        cls,
        raw_input: str,
        output_file: str,
        aspect_ratio: str = "square",
        ass_subtitle_path: Optional[str] = None,
        apply_enhancements: bool = True,
        normalize_audio: bool = True,
    ) -> List[str]:
        """
        Builds full FFmpeg command for rendering.
        """
        preset = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["square"])
        cmd = ["ffmpeg", "-y", "-i", raw_input]

        if aspect_ratio == "vertical_blurred":
            filter_complex = cls.build_ffmpeg_filtergraph(
                aspect_ratio=aspect_ratio,
                ass_subtitle_path=ass_subtitle_path,
                apply_enhancements=apply_enhancements,
            )
            cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "0:a?"])
        else:
            vf = cls.build_ffmpeg_filtergraph(
                aspect_ratio=aspect_ratio,
                ass_subtitle_path=ass_subtitle_path,
                apply_enhancements=apply_enhancements,
            )
            cmd.extend(["-vf", vf])

        # Audio normalization (EBU R128)
        if normalize_audio:
            af = (
                f"loudnorm=I={AUDIO_NORM_SETTINGS['integrated_lufs']}:"
                f"TP={AUDIO_NORM_SETTINGS['true_peak']}:"
                f"LRA={AUDIO_NORM_SETTINGS['loudness_range']}"
            )
            cmd.extend(["-af", af])

        # Video encoding settings for YouTube Shorts (H.264, 60fps capable, high compatibility)
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_file,
        ])
        return cmd

    def render_short(
        self,
        raw_video_path: str,
        output_filename: str,
        aspect_ratio: str = "square",
        ass_subtitle_path: Optional[str] = None,
    ) -> str:
        """
        Executes FFmpeg locally in cloud runner environment.
        """
        final_output = os.path.join(self.output_dir, output_filename)
        cmd = self.build_ffmpeg_render_cmd(
            raw_input=raw_video_path,
            output_file=final_output,
            aspect_ratio=aspect_ratio,
            ass_subtitle_path=ass_subtitle_path,
        )

        subprocess.run(cmd, check=True)
        return final_output
