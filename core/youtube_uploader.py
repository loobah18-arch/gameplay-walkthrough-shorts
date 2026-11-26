"""
YouTube Shorts Uploader & History State Manager.
Publishes finished Shorts to the target YouTube channel when OAuth is configured,
and records all runs into upload_history.json to enforce zero duplicate cutscenes.
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from config.settings import ROOT_DIR

UPLOAD_HISTORY_PATH = os.path.join(ROOT_DIR, "upload_history.json")


def build_youtube_client():
    """Builds an authenticated YouTube Data API v3 client from env secrets, or returns None."""
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()
    if not (client_secret and refresh_token):
        return None

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds_data = json.loads(client_secret) if client_secret.startswith("{") else {}
    app_block = creds_data.get("installed") or creds_data.get("web") or {}
    client_id = app_block.get("client_id") or os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret_val = app_block.get("client_secret") or client_secret

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret_val,
    )
    return build("youtube", "v3", credentials=creds)


class YouTubeUploader:
    """Handles channel uploads and persists non-repeating upload history."""

    def __init__(self, history_path: str = UPLOAD_HISTORY_PATH):
        self.history_path = history_path

    def load_history(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.history_path):
            return []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else data.get("entries", [])
        except Exception:
            return []

    def record_upload(
        self,
        video_file: str,
        title: str,
        game_name: str,
        source_video_id: str,
        cutscene_title: str,
        top_question: str = "",
        published: bool = False,
        youtube_id: Optional[str] = None,
        duration: float = 0.0,
    ) -> Dict[str, Any]:
        """Appends entry to upload_history.json with timestamp and metadata."""
        history = self.load_history()
        now_iso = datetime.now(timezone.utc).isoformat()

        entry = {
            "timestamp": now_iso,
            "title": title,
            "game_name": game_name,
            "source_video_id": source_video_id,
            "cutscene_title": cutscene_title,
            "top_question": top_question,
            "file": os.path.basename(video_file),
            "duration": round(duration, 2),
            "published": published,
            "youtube_id": youtube_id or "",
            "status": "published" if published else "ready_for_upload",
        }

        history.append(entry)
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            print(f"📝 Recorded in {self.history_path}: '{title}' ({source_video_id})")
        except Exception as e:
            print(f"⚠️ Warning: Failed to write to {self.history_path}: {e}")

        return entry

    def publish_short(
        self,
        video_path: str,
        title: str,
        game_name: str,
        source_video_id: str,
        cutscene_title: str,
        top_question: str = "",
        duration: float = 0.0,
        privacy_status: str = "public",
    ) -> Dict[str, Any]:
        """
        Uploads Short to YouTube if credentials exist, or saves clean metadata artifact.
        """
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
        refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

        if not (client_secret and refresh_token):
            print("\n=======================================================")
            print("ℹ️ YouTube Channel Not Connected Yet")
            print("   Output Short is saved and ready in the output directory.")
            print("   To enable automatic publishing, set GitHub Secrets:")
            print("   - YOUTUBE_CLIENT_SECRET")
            print("   - YOUTUBE_REFRESH_TOKEN")
            print("=======================================================\n")
            return self.record_upload(
                video_file=video_path,
                title=title,
                game_name=game_name,
                source_video_id=source_video_id,
                cutscene_title=cutscene_title,
                top_question=top_question,
                published=False,
                duration=duration,
            )

        print(f"🚀 Publishing Short to YouTube: '{title}'...")
        # Authenticated upload logic using google-api-python-client
        try:
            from googleapiclient.http import MediaFileUpload

            youtube = build_youtube_client()
            if youtube is None:
                raise RuntimeError("Missing YouTube OAuth client credentials")

            # Algorithm-safe description with credit and high-CTR hashtags
            clean_game = re.sub(r"[^A-Za-z0-9]+", "", game_name).lower()
            description = (
                f"{title}\n\n"
                f"Game: {game_name}\n"
                f"Source cutscene: https://www.youtube.com/watch?v={source_video_id}\n\n"
                f"#shorts #{clean_game} #gaming #cutscene #cinematic"
            )

            body = {
                "snippet": {
                    "title": title[:100],
                    "description": description,
                    "tags": ["shorts", clean_game, "gaming", "cutscene", "gameplay", "walkthrough"],
                    "categoryId": "20",  # Gaming
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
            req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            resp = req.execute()
            yt_id = resp.get("id")
            print(f"🎉 Short successfully published! URL: https://youtube.com/shorts/{yt_id}")

            return self.record_upload(
                video_file=video_path,
                title=title,
                game_name=game_name,
                source_video_id=source_video_id,
                cutscene_title=cutscene_title,
                top_question=top_question,
                published=True,
                youtube_id=yt_id,
                duration=duration,
            )
        except Exception as e:
            print(f"⚠️ YouTube upload error ({e}). Saving artifact safely without publishing.")
            return self.record_upload(
                video_file=video_path,
                title=title,
                game_name=game_name,
                source_video_id=source_video_id,
                cutscene_title=cutscene_title,
                top_question=top_question,
                published=False,
                duration=duration,
            )
