"""
Video Renderer & FFmpeg Pipeline Builder.
Handles selective segment downloading via yt-dlp and builds professional filtergraphs
for 1:1 Square (Detroit Connor reference style) and 9:16 Vertical video.
"""
import os
import re
import shlex
import subprocess
import uuid
from typing import Dict, Any, List, Optional
from config.settings import (
    ASPECT_RATIOS,
    AUDIO_NORM_SETTINGS,
    VIDEO_FILTER_ENHANCE,
    OUTPUT_DIR,
    TEMP_DIR,
)


class VideoRenderer:
    """Orchestrates cloud-side FFmpeg rendering and yt-dlp section downloads."""

    def __init__(self, output_dir: str = OUTPUT_DIR, temp_dir: str = TEMP_DIR):
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

    @staticmethod
    def _redact_cmd_for_log(cmd: List[str]) -> str:
        """Redacts proxy credentials, PO tokens, and visitor data from command logs."""
        redacted = []
        mask_next = False
        for token in cmd:
            if mask_next:
                redacted.append("***REDACTED***")
                mask_next = False
            elif token == "--proxy":
                redacted.append(token)
                mask_next = True
            elif token.startswith("youtube:po_token=") or token.startswith("youtube:visitor_data="):
                key = token.split("=", 1)[0]
                redacted.append(f"{key}=***REDACTED***")
            else:
                redacted.append(shlex.quote(token) if " " in token else token)
        return " ".join(redacted)

    @staticmethod
    def _format_hms(seconds: float) -> str:
        """Formats non-negative seconds as HH:MM:SS (preserving .mmm when fractional)."""
        total_ms = int(round(max(0.0, float(seconds)) * 1000))
        h, rem = divmod(total_ms, 3600000)
        m, rem = divmod(rem, 60000)
        s, ms = divmod(rem, 1000)
        if ms == 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    @staticmethod
    def _escape_ffmpeg_ass_path(path: str) -> str:
        """Escapes ASS path across both libavfilter filtergraph and av_get_token option levels."""
        normalized = path.replace("\\", "/")
        s1 = re.sub(r"([\\:'])", r"\\\1", normalized)
        return re.sub(r"([\\:'\[\],; ])", r"\\\1", s1)

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
        Enforces IPv4, Node.js runtime, native downloader, and web PO tokens.
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
            section = f"*{VideoRenderer._format_hms(start_time)}-{VideoRenderer._format_hms(end_time)}"
            cmd.extend(["--download-sections", section, "--force-keyframes-at-cuts"])

        if client_override:
            cmd.extend(["--extractor-args", f"youtube:player_client={client_override}"])

        is_web_client = "web" in (client_override or "")
        pot = po_token if po_token is not None else (os.environ.get("YT_PO_TOKEN") if is_web_client else None)
        vis = visitor_data if visitor_data is not None else (os.environ.get("YT_VISITOR_DATA") if is_web_client else None)
        if pot:
            cmd.extend(["--extractor-args", f"youtube:po_token=web.gvs+{pot}"])
        if vis:
            cmd.extend(["--extractor-args", f"youtube:visitor_data={vis}"])

        if use_cookies and cookies_path:
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
        return VideoRenderer.find_existing_media_file(path) is not None

    @staticmethod
    def find_existing_media_file(path: str) -> Optional[str]:
        """Returns the actual filepath on disk if the output file or an extension variant exists."""
        if os.path.isfile(path) and os.path.getsize(path) > 10000:
            return path
        base, _ = os.path.splitext(path)
        for cand in [
            path + ".webm",
            path + ".mp4",
            path + ".mkv",
            base + ".webm",
            base + ".mp4",
            base + ".mkv",
        ]:
            if os.path.isfile(cand) and os.path.getsize(cand) > 10000:
                return cand
        return None

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
        Tier 1: Apple VisionOS client (NO cookies — pristine 1080p DASH stream, bypasses SABR web blocks).
        Tier 2: Android / Android VR client (NO cookies — fast fallback).
        Tier 3: Authenticated download with cookies + PO Token across web_safari, mweb, web.
        Tier 4: iOS / TV client without cookies.
        Tier 5: Full-file progressive native download + frame-accurate ffmpeg cut (with cleanup).
        """
        if end_time <= start_time:
            raise ValueError(f"end_time ({end_time}) must be greater than start_time ({start_time})")

        def run_ytdlp(cmd: List[str]) -> bool:
            print(f"▶️ Executing: {cls._redact_cmd_for_log(cmd)}")
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if res.stdout:
                print(res.stdout)
            return res.returncode == 0 and cls.check_file_exists(output_filepath)

        # Tier 1: Residential Proxy Routing (if configured)
        p = proxy or os.environ.get("YOUTUBE_PROXY")
        if p:
            print("🌐 [Tier 1] Attempting download via YOUTUBE_PROXY (residential IP)...")
            cmd1 = cls.build_ytdlp_download_cmd(
                video_url=video_url,
                start_time=start_time,
                end_time=end_time,
                output_filepath=output_filepath,
                cookies_path=cookies_path,
                proxy=p,
                client_override="web,mweb",
                use_cookies=True,
                po_token=po_token,
                visitor_data=visitor_data,
                format_spec="bestvideo[height<=1080]+bestaudio/best[height<=1080]/18/b",
                use_download_sections=True,
            )
            if run_ytdlp(cmd1):
                found = cls.find_existing_media_file(output_filepath)
                if found:
                    print(f"✅ [Tier 1] Successfully downloaded clip via Proxy: {found}")
                    return found

        # Tier 2: PO Token + bgutil Docker service (web,mweb with cookies)
        # Uses local bgutil container on :4416 if healthy to generate fresh gvs PO tokens
        if cookies_path and os.path.isfile(cookies_path):
            print("🎟️ [Tier 2] Trying PO Token + cookies with bgutil service (web,mweb)...")
            cmd2 = cls.build_ytdlp_download_cmd(
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
                format_spec="bestvideo[height<=1080]+bestaudio/best[height<=1080]/18/b",
                use_download_sections=True,
            )
            if run_ytdlp(cmd2):
                found = cls.find_existing_media_file(output_filepath)
                if found:
                    print(f"✅ [Tier 2] PO Token section download succeeded: {found}")
                    return found

            # Tier 2b: Native full-file download with web/mweb (no --download-sections)
            # Avoids FFmpeg HTTP range 403 Forbidden errors
            print("🛡️ [Tier 2b] Trying native full-file download with PO token (web,mweb)...")
            temp_full2 = os.path.join(
                os.path.dirname(os.path.abspath(output_filepath)),
                f"full_src_pot_{uuid.uuid4().hex[:8]}.mp4",
            )
            cmd2b = cls.build_ytdlp_download_cmd(
                video_url=video_url,
                start_time=None,
                end_time=None,
                output_filepath=temp_full2,
                cookies_path=cookies_path,
                proxy=proxy,
                client_override="web,mweb",
                use_cookies=True,
                po_token=po_token,
                visitor_data=visitor_data,
                format_spec="bestvideo[height<=1080]+bestaudio/best[height<=1080]/18/b",
                use_download_sections=False,
            )
            print(f"▶️ Executing: {cls._redact_cmd_for_log(cmd2b)}")
            res2b = subprocess.run(cmd2b, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if res2b.stdout:
                print(res2b.stdout)
            actual_full2 = cls.find_existing_media_file(temp_full2)
            try:
                if actual_full2 and os.path.isfile(actual_full2):
                    print(f"✂️ Cutting section {start_time}s to {end_time}s via frame-accurate ffmpeg...")
                    cut_cmd = [
                        "ffmpeg", "-y",
                        "-ss", str(start_time),
                        "-to", str(end_time),
                        "-i", actual_full2,
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                        "-c:a", "aac", "-b:a", "192k",
                        output_filepath,
                    ]
                    subprocess.run(cut_cmd, check=True)
                    found = cls.find_existing_media_file(output_filepath)
                    if found:
                        print(f"✅ [Tier 2b] Successfully extracted clip from PO Token full download: {found}")
                        return found
            finally:
                if actual_full2 and os.path.isfile(actual_full2):
                    try:
                        os.remove(actual_full2)
                    except OSError:
                        pass

        # Tier 3: Apple VisionOS / iOS HLS client (NO cookies)
        print("🍎 [Tier 3] Trying Apple VisionOS / iOS HLS client (no cookies)...")
        for client in ["visionos", "ios", "android_vr"]:
            cmd3 = cls.build_ytdlp_download_cmd(
                video_url=video_url,
                start_time=start_time,
                end_time=end_time,
                output_filepath=output_filepath,
                cookies_path=None,
                proxy=proxy,
                client_override=client,
                use_cookies=False,
                format_spec="bestvideo[height<=1080]+bestaudio/best[height<=1080]/18/b",
                use_download_sections=True,
            )
            if run_ytdlp(cmd3):
                found = cls.find_existing_media_file(output_filepath)
                if found:
                    print(f"✅ [Tier 3] Apple/Mobile client section download succeeded ({client}): {found}")
                    return found

        # Tier 4: CDN 403 Bypass (720p / progressive format 22 / 18 / b)
        print("🛡️ [Tier 4] Fallback: Progressive 720p/360p native download to bypass CDN 403...")
        temp_full = os.path.join(
            os.path.dirname(os.path.abspath(output_filepath)),
            f"full_source_{uuid.uuid4().hex[:8]}.mp4",
        )
        cmd4 = cls.build_ytdlp_download_cmd(
            video_url=video_url,
            start_time=None,
            end_time=None,
            output_filepath=temp_full,
            cookies_path=cookies_path if (cookies_path and os.path.isfile(cookies_path)) else None,
            proxy=proxy,
            client_override="web,mweb,android",
            use_cookies=bool(cookies_path and os.path.isfile(cookies_path)),
            format_spec="22/18/best[height<=720]/b",
            use_download_sections=False,
        )
        print(f"▶️ Executing: {cls._redact_cmd_for_log(cmd4)}")
        res4 = subprocess.run(cmd4, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if res4.stdout:
            print(res4.stdout)

        actual_full = cls.find_existing_media_file(temp_full)
        try:
            if actual_full and os.path.isfile(actual_full):
                print(f"✂️ Cutting section {start_time}s to {end_time}s via frame-accurate ffmpeg...")
                cut_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start_time),
                    "-to", str(end_time),
                    "-i", actual_full,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-c:a", "aac", "-b:a", "192k",
                    output_filepath,
                ]
                subprocess.run(cut_cmd, check=True)
                found = cls.find_existing_media_file(output_filepath)
                if found:
                    print(f"✅ [Tier 4] Successfully extracted clip from progressive download: {found}")
                    return found
        finally:
            if actual_full and os.path.isfile(actual_full):
                try:
                    os.remove(actual_full)
                except OSError:
                    pass

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
        - 1:1 Square (crops widescreen/portrait safely to centered square)
        - 9:16 Vertical Center-Crop
        - 9:16 Vertical Blurred Background
        """
        preset = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["vertical_letterbox"])
        target_w = preset["width"]
        target_h = preset["height"]

        if aspect_ratio == "vertical_letterbox":
            # 16:9 widescreen cutscene centered on 1080x1920 with pure black bars on top and bottom
            # (Matches reference style xoJydV-xKVw: text on top black bar, zero overlap with video)
            filters = [
                f"scale={target_w}:-2:force_original_aspect_ratio=decrease",
                "setsar=1",
            ]
            if apply_enhancements:
                filters.append(VIDEO_FILTER_ENHANCE)
            filters.append(f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black")
            if ass_subtitle_path and os.path.isfile(ass_subtitle_path):
                escaped_sub = cls._escape_ffmpeg_ass_path(ass_subtitle_path)
                filters.append(f"ass={escaped_sub}")
            return ",".join(filters)

        elif aspect_ratio == "square_letterbox":
            # 1:1 square cutscene centered on 1080x1920 with pure black bars on top and bottom
            filters = [
                f"scale={target_w}:{target_w}:force_original_aspect_ratio=increase",
                f"crop={target_w}:{target_w}",
                "setsar=1",
            ]
            if apply_enhancements:
                filters.append(VIDEO_FILTER_ENHANCE)
            filters.append(f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black")
            if ass_subtitle_path and os.path.isfile(ass_subtitle_path):
                escaped_sub = cls._escape_ffmpeg_ass_path(ass_subtitle_path)
                filters.append(f"ass={escaped_sub}")
            return ",".join(filters)

        if aspect_ratio == "vertical_blurred":
            bg_filter = (
                f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"setsar=1,crop={target_w}:{target_h},boxblur=25:5,eq=brightness=-0.08:contrast=1.05[bg]"
            )
            fg_enhance = f",{VIDEO_FILTER_ENHANCE}" if apply_enhancements else ""
            fg_filter = f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,setsar=1{fg_enhance}[fg]"
            overlay_filter = "[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
            if ass_subtitle_path and os.path.isfile(ass_subtitle_path):
                escaped_sub = cls._escape_ffmpeg_ass_path(ass_subtitle_path)
                sub_filter = f";[base]ass={escaped_sub}[v]"
            else:
                sub_filter = ";[base]copy[v]"
            return f"{bg_filter};{fg_filter};{overlay_filter}{sub_filter}"

        filters = [
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase",
            "setsar=1",
            f"crop={target_w}:{target_h}",
        ]

        if apply_enhancements:
            filters.append(VIDEO_FILTER_ENHANCE)

        if ass_subtitle_path and os.path.isfile(ass_subtitle_path):
            escaped_sub = cls._escape_ffmpeg_ass_path(ass_subtitle_path)
            filters.append(f"ass={escaped_sub}")

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

        if normalize_audio:
            af = (
                f"loudnorm=I={AUDIO_NORM_SETTINGS['integrated_lufs']}:"
                f"TP={AUDIO_NORM_SETTINGS['true_peak']}:"
                f"LRA={AUDIO_NORM_SETTINGS['loudness_range']}"
            )
            cmd.extend(["-af", af])

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
