"""
Lightweight walkthrough and cutscene metadata & transcript fetcher.
Designed to run with minimal CPU and memory on Termux (zero video downloading).
"""
import os
import re
import glob
import json
import subprocess
from typing import Dict, Any, List, Optional
from config.settings import TEMP_DIR
from core.cookie_manager import CookieManager


class WalkthroughFetcher:
    """Fetches YouTube walkthrough metadata and transcripts using yt-dlp."""

    def __init__(self, temp_dir: str = TEMP_DIR):
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)

    @staticmethod
    def get_proxy_args(proxy: Optional[str] = None) -> List[str]:
        """Returns yt-dlp arguments for proxy if provided or present in environment."""
        p = proxy or os.environ.get("YOUTUBE_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
        if p:
            return ["--proxy", p]
        return []

    def fetch_video_info(
        self, url: str, cookies_path: Optional[str] = None, proxy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves video metadata, chapters, and available resolutions without downloading media.
        """
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--skip-download",
            "--no-playlist",
        ]
        cmd.extend(CookieManager.get_ytdlp_cookie_args(cookies_path))
        cmd.extend(self.get_proxy_args(proxy))
        cmd.append(url)

        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)

        # Extract max available height and 60fps flag
        formats = data.get("formats", [])
        max_height = 0
        has_60fps = False
        for f in formats:
            h = f.get("height") or 0
            fps = f.get("fps") or 0
            if h > max_height:
                max_height = h
            if fps >= 50:
                has_60fps = True

        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "channel": data.get("channel") or data.get("uploader"),
            "duration": data.get("duration", 0),
            "view_count": data.get("view_count", 0),
            "description": data.get("description", ""),
            "max_resolution": f"{max_height}p" + ("60" if has_60fps else ""),
            "max_height": max_height,
            "has_60fps": has_60fps,
            "chapters": data.get("chapters") or [],
            "url": f"https://www.youtube.com/watch?v={data.get('id')}",
        }

    def fetch_transcript(
        self,
        url: str,
        video_id: str,
        cookies_path: Optional[str] = None,
        proxy: Optional[str] = None,
        lang: str = "en",
    ) -> List[Dict[str, Any]]:
        """
        Downloads VTT subtitles and parses them into timestamped cue dicts.
        Does not download video streams.
        """
        out_template = os.path.join(self.temp_dir, f"sub_{video_id}_%(id)s")
        cmd = [
            "yt-dlp",
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang", lang,
            "--skip-download",
            "-o", out_template,
        ]
        cmd.extend(CookieManager.get_ytdlp_cookie_args(cookies_path))
        cmd.extend(self.get_proxy_args(proxy))
        cmd.append(url)

        subprocess.run(cmd, capture_output=True, text=True, check=False)

        pattern = os.path.join(self.temp_dir, f"sub_{video_id}*.vtt")
        matched = glob.glob(pattern)

        if not matched:
            return []

        # Parse the newest matching file
        vtt_file = sorted(matched, key=os.path.getmtime, reverse=True)[0]
        try:
            with open(vtt_file, "r", encoding="utf-8") as f:
                content = f.read()
            return self.parse_vtt_content(content)
        finally:
            # Clean up temporary subtitle files
            for m in matched:
                try:
                    os.remove(m)
                except OSError:
                    pass

    @staticmethod
    def parse_timestamp(ts: str) -> float:
        """Parses VTT timestamp format (HH:MM:SS.mmm or MM:SS.mmm) into seconds."""
        parts = ts.strip().split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return float(ts)

    @classmethod
    def parse_vtt_content(cls, vtt_text: str) -> List[Dict[str, Any]]:
        """
        Parses raw WebVTT content, stripping tags and removing duplicates.
        """
        cues = []
        time_pattern = re.compile(
            r"(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})"
        )

        blocks = vtt_text.split("\n\n")
        last_text = ""

        for block in blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue

            time_match = None
            text_lines = []

            for line in lines:
                m = time_pattern.search(line)
                if m:
                    time_match = m
                elif not line.startswith("WEBVTT") and not line.startswith("NOTE") and not line.isdigit():
                    # Strip HTML / formatting tags like <c>, </c>, <v Speaker>
                    clean_line = re.sub(r"<[^>]+>", "", line).strip()
                    if clean_line:
                        text_lines.append(clean_line)

            if time_match and text_lines:
                start_sec = cls.parse_timestamp(time_match.group(1))
                end_sec = cls.parse_timestamp(time_match.group(2))
                raw_text = " ".join(text_lines)

                # Skip identical consecutive text cues produced by rolling auto-captions
                if raw_text == last_text:
                    continue

                cues.append({
                    "start": round(start_sec, 2),
                    "end": round(end_sec, 2),
                    "text": raw_text,
                })
                last_text = raw_text

        return cues

    def search_walkthroughs(
        self, query: str, max_results: int = 5, cookies_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches YouTube for gameplay walkthroughs / game movies.
        """
        search_query = f"ytsearch{max_results}:{query} 4K 60fps walkthrough cutscenes"
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--flat-playlist",
            "--skip-download",
            search_query,
        ]
        cmd.extend(CookieManager.get_ytdlp_cookie_args(cookies_path))

        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        results = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                results.append({
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "channel": item.get("channel") or item.get("uploader"),
                    "duration": item.get("duration"),
                    "url": f"https://www.youtube.com/watch?v={item.get('id')}",
                })
            except json.JSONDecodeError:
                pass
        return results
