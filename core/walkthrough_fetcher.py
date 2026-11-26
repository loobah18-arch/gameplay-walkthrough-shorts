"""
Lightweight walkthrough and cutscene metadata & transcript fetcher.
Designed to run with minimal CPU and memory on Termux (zero video downloading).
"""
import os
import re
import glob
import html
import json
import uuid
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
        base_cmd = [
            "yt-dlp",
            "-4",
            "--js-runtimes", "node",
            "--remote-components", "ejs:github",
            "--extractor-args", "youtube:player_client=web,mweb",
            "--dump-json",
            "--skip-download",
            "--no-playlist",
            "--socket-timeout", "45",
        ]
        proxy_args = self.get_proxy_args(proxy)
        cookie_args = CookieManager.get_ytdlp_cookie_args(cookies_path)

        cmd = [*base_cmd, *cookie_args, *proxy_args, url]

        res = None
        stdout = ""
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            stdout = (res.stdout or "").strip()
        except subprocess.CalledProcessError as e:
            res = e
            stdout = (getattr(e, "stdout", "") or "").strip()

        if not stdout and cookie_args:
            # Fallback without cookies while preserving proxy settings
            cmd_fallback = [*base_cmd, "--no-cookies", *proxy_args, url]
            try:
                res = subprocess.run(cmd_fallback, capture_output=True, text=True, check=True)
                stdout = (res.stdout or "").strip()
            except subprocess.CalledProcessError as e2:
                res = e2
                stdout = (getattr(e2, "stdout", "") or "").strip()

        if not stdout:
            err_msg = str(getattr(res, "stderr", "") or res or "").strip().replace("\n", " ")[:200]
            print(f"⚠️ [fetch_video_info] Failed for {url}: {err_msg}")
            return {}

        try:
            data = json.loads(stdout)
        except Exception as e:
            print(f"⚠️ [fetch_video_info] JSON decode error for {url}: {e}")
            return {}

        # Extract max available height and 60fps flag
        formats = data.get("formats") or []
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
            "duration": data.get("duration") or 0,
            "view_count": data.get("view_count") or 0,
            "description": data.get("description") or "",
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
        job_tag = uuid.uuid4().hex[:8]
        safe_vid = re.sub(r"[^A-Za-z0-9_-]", "", video_id or "vid") or "vid"
        prefix = f"sub_{safe_vid}_{job_tag}"
        out_template = os.path.join(self.temp_dir, f"{prefix}_%(id)s")
        sub_langs = lang if ("," in lang or "*" in lang) else f"{lang}.*,{lang}"

        base_cmd = [
            "yt-dlp",
            "-4",
            "--js-runtimes", "node",
            "--extractor-args", "youtube:player_client=android,ios,mweb",
            "--no-playlist",
            "--write-auto-sub",
            "--write-sub",
            "--sub-format", "vtt",
            "--sub-lang", sub_langs,
            "--skip-download",
            "-o", out_template,
        ]
        proxy_args = self.get_proxy_args(proxy)
        cookie_args = CookieManager.get_ytdlp_cookie_args(cookies_path)

        pattern = os.path.join(self.temp_dir, f"{prefix}*.vtt")

        try:
            subprocess.run(
                [*base_cmd, *cookie_args, *proxy_args, url],
                capture_output=True,
                text=True,
                check=False,
            )
            matched = glob.glob(pattern)

            # Retry without cookies if authenticated request yielded no subtitles
            if not matched and cookie_args:
                subprocess.run(
                    [*base_cmd, "--no-cookies", *proxy_args, url],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                matched = glob.glob(pattern)

            if not matched:
                return []

            vtt_file = sorted(matched, key=os.path.getmtime, reverse=True)[0]
            with open(vtt_file, "r", encoding="utf-8") as f:
                content = f.read()
            return self.parse_vtt_content(content)
        finally:
            for leftover in glob.glob(os.path.join(self.temp_dir, f"{prefix}*")):
                try:
                    os.remove(leftover)
                except OSError:
                    pass

    @staticmethod
    def parse_timestamp(ts: str) -> float:
        """Parses VTT timestamp format (HH:MM:SS.mmm or MM:SS.mmm) into seconds."""
        cleaned = ts.strip().replace(",", ".")
        parts = cleaned.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return float(cleaned)

    @classmethod
    def parse_vtt_content(cls, vtt_text: str) -> List[Dict[str, Any]]:
        """
        Parses raw WebVTT content, stripping formatting tags/entities and removing rolling duplicates.
        """
        if not vtt_text:
            return []

        cues = []
        time_pattern = re.compile(
            r"(\d{1,3}:\d{2}:\d{2}[.,]\d{3}|\d{1,3}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,3}:\d{2}:\d{2}[.,]\d{3}|\d{1,3}:\d{2}[.,]\d{3})"
        )

        normalized = vtt_text.replace("\r\n", "\n").replace("\r", "\n")
        blocks = re.split(r"\n\s*\n", normalized.strip())
        last_text = ""

        for block in blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not lines:
                continue

            head = lines[0]
            if head.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
                continue

            time_match = None
            text_lines = []

            for line in lines:
                if time_match is None:
                    m = time_pattern.search(line)
                    if m:
                        time_match = m
                    # Ignore cue identifiers appearing before timestamp line
                    continue

                clean_line = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
                if clean_line:
                    text_lines.append(clean_line)

            if time_match and text_lines:
                start_sec = cls.parse_timestamp(time_match.group(1))
                end_sec = cls.parse_timestamp(time_match.group(2))
                raw_text = " ".join(text_lines)

                # Skip identical consecutive lines or tiny transition flash cues
                if raw_text == last_text:
                    continue
                if cues and (end_sec - start_sec) <= 0.05 and raw_text in last_text:
                    continue

                cues.append({
                    "start": round(start_sec, 2),
                    "end": round(end_sec, 2),
                    "text": raw_text,
                })
                last_text = raw_text

        return cues

    def search_walkthroughs(
        self,
        query: str,
        max_results: int = 5,
        cookies_path: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches YouTube for gameplay walkthroughs / game movies.
        """
        search_query = f"ytsearch{max_results}:{query} 4K 60fps walkthrough cutscenes"
        cmd = [
            "yt-dlp",
            "-4",
            "--js-runtimes", "node",
            "--dump-json",
            "--flat-playlist",
            "--skip-download",
            search_query,
        ]
        cmd.extend(CookieManager.get_ytdlp_cookie_args(cookies_path))
        cmd.extend(self.get_proxy_args(proxy))

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
                    "duration": item.get("duration") or 0,
                    "url": f"https://www.youtube.com/watch?v={item.get('id')}",
                })
            except json.JSONDecodeError:
                pass
        return results
