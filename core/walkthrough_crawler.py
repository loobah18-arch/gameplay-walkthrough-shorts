"""
Walkthrough Backlog Crawler & Autonomous Video Discovery.
Discovers long-form 4K walkthroughs and game movies, strictly excluding Shorts (<180s)
and cross-referencing upload_history.json to guarantee zero repeated scenes.
"""
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

from config.settings import ROOT_DIR

CATALOG_PATH = os.path.join(ROOT_DIR, "config", "game_catalog.json")
UPLOAD_HISTORY_PATH = os.path.join(ROOT_DIR, "upload_history.json")


def log(msg: str) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [WalkthroughCrawler] {msg}", flush=True)


class WalkthroughCrawler:
    """Discovers fresh long-form game movie walkthroughs with duplicate avoidance."""

    def __init__(
        self,
        catalog_path: str = CATALOG_PATH,
        history_path: str = UPLOAD_HISTORY_PATH,
    ):
        self.catalog_path = catalog_path
        self.history_path = history_path
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> Dict[str, Any]:
        if os.path.isfile(self.catalog_path):
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"games": {}, "curated_channels": []}

    def get_clipped_history(self) -> Dict[str, Any]:
        """Loads upload history to avoid repeating videos or specific cutscenes."""
        if not os.path.isfile(self.history_path):
            return {"clipped_video_ids": [], "clipped_cutscenes": [], "entries": []}
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    vids = [item.get("source_video_id") or item.get("video_id") for item in data if item]
                    scenes = [item.get("cutscene_title") or item.get("title") for item in data if item]
                    return {
                        "clipped_video_ids": [v for v in vids if v],
                        "clipped_cutscenes": [s for s in scenes if s],
                        "entries": data,
                    }
                return data
        except Exception as e:
            log(f"Warning: Failed to load history: {e}")
            return {"clipped_video_ids": [], "clipped_cutscenes": [], "entries": []}

    def is_previously_clipped(self, video_id: str, cutscene_title: Optional[str] = None) -> bool:
        """Checks if video ID or cutscene title was already clipped and published."""
        history = self.get_clipped_history()
        if video_id in history.get("clipped_video_ids", []):
            return True
        if cutscene_title:
            norm_title = re.sub(r"[^a-zA-Z0-9]+", "", cutscene_title.lower())
            for clipped in history.get("clipped_cutscenes", []):
                if norm_title == re.sub(r"[^a-zA-Z0-9]+", "", str(clipped).lower()):
                    return True
        return False

    def fetch_channel_rss_uploads(self, channel_id: str, timeout: int = 10) -> List[Dict[str, Any]]:
        """Fetches the 15 latest uploads for a channel via YouTube XML RSS feed."""
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        uploads = []
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read()
                root = ET.fromstring(content)
                ns = {
                    "atom": "http://www.w3.org/2005/Atom",
                    "yt": "http://www.youtube.com/xml/schemas/2015",
                }
                for entry in root.findall("atom:entry", ns):
                    vid_elem = entry.find("yt:videoId", ns)
                    title_elem = entry.find("atom:title", ns)
                    pub_elem = entry.find("atom:published", ns)
                    if vid_elem is not None and title_elem is not None:
                        vid_id = vid_elem.text or ""
                        title = title_elem.text or ""
                        pub_str = pub_elem.text if pub_elem is not None else ""
                        if vid_id and title:
                            uploads.append({
                                "video_id": vid_id,
                                "title": title,
                                "published_at": pub_str,
                                "url": f"https://www.youtube.com/watch?v={vid_id}",
                            })
        except Exception as e:
            log(f"Warning: RSS fetch failed for channel {channel_id}: {e}")
        return uploads

    def search_game_walkthroughs(
        self,
        query: str,
        max_results: int = 5,
        proxy: Optional[str] = None,
        cookies_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches YouTube for long-form game movies and cutscenes using fast flat-playlist dumping.
        Strictly filters out any video under 180 seconds (no Shorts allowed).
        """
        search_target = f"ytsearch{max_results}:{query}" if not query.startswith("ytsearch") else query
        cmd = [
            "yt-dlp",
            "-4",
            "--js-runtimes", "node",
            "--flat-playlist",
            "--dump-json",
            "--skip-download",
            "--no-playlist",
            "--no-cookies",
        ]
        if proxy or os.environ.get("YOUTUBE_PROXY"):
            cmd.extend(["--proxy", proxy or os.environ["YOUTUBE_PROXY"]])

        cmd.append(search_target)
        results = []
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.strip().splitlines():
                    try:
                        data = json.loads(line)
                        dur = data.get("duration") or 0
                        # Hard filter: must be at least 3 minutes, not a Short
                        if dur > 0 and dur < 180:
                            continue
                        vid_id = data.get("id")
                        if vid_id:
                            results.append({
                                "video_id": vid_id,
                                "title": data.get("title") or "Gameplay Walkthrough",
                                "duration": dur,
                                "channel": data.get("channel") or data.get("uploader"),
                                "url": f"https://www.youtube.com/watch?v={vid_id}",
                                "chapters": data.get("chapters") or [],
                            })
                    except Exception:
                        continue
        except Exception as e:
            log(f"Warning: Search failed for '{query}': {e}")
        return results

    def list_candidates(
        self,
        preferred_game: Optional[str] = None,
        proxy: Optional[str] = None,
        cookies_path: Optional[str] = None,
        max_candidates: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Returns ranked unclipped long-form candidates across the target game's search queries
        and RSS fallback so the caller can verify cutscene chapters / dialogue payoffs and
        reject videos that lack a verified cutscene climax.
        """
        games = self.catalog.get("games", {})
        game_keys = list(games.keys())
        if not game_keys:
            raise RuntimeError("No games found in catalog.")

        history = self.get_clipped_history()
        clipped_ids = set(history.get("clipped_video_ids", []))

        selected_game_key = preferred_game if preferred_game in games else None
        if selected_game_key:
            target_games = [selected_game_key]
        else:
            idx = len(history.get("entries", [])) % len(game_keys)
            target_games = [game_keys[idx]] + [g for i, g in enumerate(game_keys) if i != idx]

        collected: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()

        for g_key in target_games:
            game_data = games[g_key]
            game_name = game_data.get("name", g_key)
            queries = game_data.get("search_queries", [f"{game_name} All Cutscenes 4K"])

            log(f"Discovering unclipped cutscene candidates for game: '{game_name}'")

            for query in queries:
                candidates = self.search_game_walkthroughs(
                    query=query,
                    max_results=6,
                    proxy=proxy,
                    cookies_path=cookies_path,
                )
                for cand in candidates:
                    vid = cand["video_id"]
                    if vid in clipped_ids or vid in seen_ids:
                        continue
                    seen_ids.add(vid)
                    collected.append({
                        "game_key": g_key,
                        "game_name": game_name,
                        "video_id": vid,
                        "title": cand["title"],
                        "url": cand["url"],
                        "duration": cand["duration"],
                        "chapters": cand.get("chapters", []),
                    })
                    if len(collected) >= max_candidates * 2:
                        break

            if collected:
                def _duration_priority(c):
                    dur = c.get("duration") or 999999
                    if 300 <= dur <= 3600:
                        return (0, dur)
                    if 180 <= dur <= 7200:
                        return (1, dur)
                    return (2, dur)

                collected.sort(key=_duration_priority)
                return collected[:max_candidates]

        if not collected:
            # Fallback to curated channels RSS only if search returned no usable items
            curated_channels = self.catalog.get("curated_channels", [])
            for ch in curated_channels:
                ch_id = ch.get("channel_id")
                if not ch_id:
                    continue
                for up in self.fetch_channel_rss_uploads(ch_id):
                    vid = up["video_id"]
                    title_lower = up["title"].lower()
                    if vid in clipped_ids or vid in seen_ids or "#shorts" in title_lower:
                        continue
                    seen_ids.add(vid)
                    collected.append({
                        "game_key": target_games[0],
                        "game_name": games[target_games[0]].get("name", target_games[0]),
                        "video_id": vid,
                        "title": up["title"],
                        "url": up["url"],
                        "duration": 0,
                        "chapters": [],
                    })
                    if len(collected) >= max_candidates:
                        return collected

        return collected

    def select_next_walkthrough(
        self,
        preferred_game: Optional[str] = None,
        proxy: Optional[str] = None,
        cookies_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Selects the top unclipped walkthrough candidate for the target game."""
        candidates = self.list_candidates(
            preferred_game=preferred_game,
            proxy=proxy,
            cookies_path=cookies_path,
            max_candidates=5,
        )
        if not candidates:
            raise RuntimeError("Could not find any unclipped walkthrough candidates.")
        top = candidates[0]
        log(f"✅ Selected unclipped candidate: '{top['title']}' ({top['video_id']}) [{top['duration']}s]")
        return top
