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
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        output_filepath: str = "temp/clip.mp4",
        cookies_path: Optional[str] = None,
        proxy: Optional[str] = None,
        client_override: str = "web,mweb",
        use_cookies: bool = True,
        po_token: Optional[str] = None,
        visitor_data: Optional[str] = None,
        format_spec: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/22/18/b",
        use_download_sections: bool = True,
    ) -> List[str]:
        """
        Builds yt-dlp command using --download-sections or full file ingestion.
        Enforces IPv4, Node.js runtime, native downloader, and PO tokens.
        """
        cmd = [
            "yt-dlp",
            "-4",
            "--js-runtimes", "node",
            "--remote-components", "ejs:github",
            "--no-playlist",
            "--socket-timeout", "45",
        ]

        if use_download_sections and start_time is not None and end_time is not None:
            def to_hms(s: float) -> str:
                h = int(s // 3600)
                m = int((s % 3600) // 60)
                sec = int(s % 60)
                return f"{h:02d}:{m:02d}:{sec:02d}"

            section = f"*{to_hms(start_time)}-{to_hms(end_time)}"
            cmd.extend(["--download-sections", section, "--force-keyframes-at-cuts"])

        if client_override:
            cmd.extend(["--extractor-args", f"youtube:player_client={client_override}"])

        pot = po_token or os.environ.get("YT_PO_TOKEN")
        vis = visitor_data or os.environ.get("YT_VISITOR_DATA")
        if pot:
            cmd.extend(["--extractor-args", f"youtube:po_token=web.gvs+{pot}"])
        if vis:
            cmd.extend(["--extractor-args", f"youtube:visitor_data={vis}"])

        if use_cookies and cookies_path and os.path.isfile(cookies_path):
            cmd.extend(["--cookies", cookies_path])
        elif not use_cookies:
            cmd.append("--no-cookies")

        cmd.extend(["--downloader", "native"])
        cmd.extend(["--format", format_spec])
        cmd.extend(["-o", output_filepath])

        p = proxy or os.environ.get("YOUTUBE_PROXY")
        if p:
            cmd.extend(["--proxy", p])

        cmd.append(video_url)
        return cmd

    @staticmethod
    def check_file_exists(path: str) -> bool:
        """Returns True if the output file or a common media extension variant exists and is non-empty."""
        if os.path.isfile(path) and os.path.getsize(path) > 10000:
            return True
        base, _ = os.path.splitext(path)
        for ext in [".mp4", ".mkv", ".webm"]:
            cand = base + ext
            if os.path.isfile(cand) and os.path.getsize(cand) > 10000:
                return True
        return False

    @classmethod
    def download_video_section(
        cls,
        video_url: str,
        start_time: float,
        end_time: float,
        output_filepath: str,
        cookies_path: Optional[str] = None,
        proxy: Optional[str] = None,
        po_token: Optional[str] = None,
        visitor_data: Optional[str] = None,
    ) -> str:
        """
        Multi-tier cascading downloader:
        Tier 1: Section download with cookies + PO Token + web/mweb.
        Tier 2: Section download with progressive format bypass (22/18).
        Tier 3: Mobile client (ios,android) WITHOUT cookies.
        Tier 4: VisionOS client fallback.
        Tier 5: Full native download format 22/18 + local ffmpeg cut.
        """
        def run_ytdlp(cmd: List[str]) -> bool:
            print(f"▶️ Executing: {' '.join(cmd)}")
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if res.stdout:
                print(res.stdout)
            return res.returncode == 0 and cls.check_file_exists(output_filepath)

        # Tier 1: Cookies with web/mweb and PO token
        print("🔄 [Tier 1] Trying section download with cookies + PO Token (web,mweb)...")
        cmd1 = cls.build_ytdlp_download_cmd(
            video_url=video_url,
            start_time=start_time,
            end_time=end_time,
            output_filepath=output_filepath,
            cookies_path=cookies_path,
            proxy=proxy,
            client_override="web,mweb",
            use_cookies=True,
            po_token=po_token,
            visitor_data=visitor_data,
            format_spec="bestvideo[height<=1080]+bestaudio/best[height<=1080]/22/18/b",
            use_download_sections=True,
        )
        if run_ytdlp(cmd1):
            print("✅ [Tier 1] Section download succeeded with cookies.")
            return output_filepath

        # Tier 2: Progressive format 22 / 18 section download
        print("🔄 [Tier 2] Trying progressive format bypass (22/18) section download...")
        cmd2 = cls.build_ytdlp_download_cmd(
            video_url=video_url,
            start_time=start_time,
            end_time=end_time,
            output_filepath=output_filepath,
            cookies_path=cookies_path,
            proxy=proxy,
            client_override="android,mweb,web",
            use_cookies=True,
            po_token=po_token,
            visitor_data=visitor_data,
            format_spec="22/18/best[height<=720]/b",
            use_download_sections=True,
        )
        if run_ytdlp(cmd2):
            print("✅ [Tier 2] Section download succeeded with progressive format.")
            return output_filepath

        # Tier 3: Native iOS/Android mobile client (NO cookies to prevent skipping)
        print("🔄 [Tier 3] Falling back to native iOS/Android client without cookies...")
        cmd3 = cls.build_ytdlp_download_cmd(
            video_url=video_url,
            start_time=start_time,
            end_time=end_time,
            output_filepath=output_filepath,
            cookies_path=None,
            proxy=proxy,
            client_override="ios,android",
            use_cookies=False,
            format_spec="bestvideo[height<=1080]+bestaudio/best[height<=1080]/22/18/b",
            use_download_sections=True,
        )
        if run_ytdlp(cmd3):
            print("✅ [Tier 3] Download succeeded via mobile client.")
            return output_filepath

        # Tier 4: Apple VisionOS fallback
        print("🔄 [Tier 4] Falling back to VisionOS client...")
        cmd4 = cls.build_ytdlp_download_cmd(
            video_url=video_url,
            start_time=start_time,
            end_time=end_time,
            output_filepath=output_filepath,
            cookies_path=None,
            proxy=proxy,
            client_override="visionos",
            use_cookies=False,
            use_download_sections=True,
        )
        if run_ytdlp(cmd4):
            print("✅ [Tier 4] Download succeeded via VisionOS client.")
            return output_filepath

        # Tier 5: Full-file progressive native download + local ffmpeg cut
        print("🔄 [Tier 5] Fallback: Full-file progressive native download + local ffmpeg cut...")
        temp_full = os.path.join(os.path.dirname(output_filepath), "full_source.mp4")
        cmd5 = cls.build_ytdlp_download_cmd(
            video_url=video_url,
            start_time=None,
            end_time=None,
            output_filepath=temp_full,
            cookies_path=cookies_path,
            proxy=proxy,
            client_override="android,mweb,web",
            use_cookies=True,
            po_token=po_token,
            visitor_data=visitor_data,
            format_spec="22/18/best[height<=720]/b",
            use_download_sections=False,
        )
        print(f"▶️ Executing: {' '.join(cmd5)}")
        res5 = subprocess.run(cmd5, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if res5.stdout:
            print(res5.stdout)

        actual_full = temp_full
        if not os.path.isfile(actual_full):
            base, _ = os.path.splitext(temp_full)
            for cand in [base + ".mp4", base + ".webm", base + ".mkv"]:
                if os.path.isfile(cand) and os.path.getsize(cand) > 10000:
                    actual_full = cand
                    break

        if os.path.isfile(actual_full) and os.path.getsize(actual_full) > 10000:
            print(f"✂️ Cutting section {start_time}s to {end_time}s locally via ffmpeg...")
            cut_cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-to", str(end_time),
                "-i", actual_full,
                "-c", "copy",
                output_filepath
            ]
            subprocess.run(cut_cmd, check=True)
            if cls.check_file_exists(output_filepath):
                print("✅ [Tier 5] Successfully extracted clip from full download.")
                return output_filepath

        raise RuntimeError(f"All download tiers failed for {video_url}")

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
