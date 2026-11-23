"""
Cloud Dispatcher for GitHub Actions CI/CD.
Orchestrates remote server-side rendering so zero heavy media processing runs on the phone.
"""
import json
import subprocess
from typing import Dict, Any, Optional
from config.settings import DEFAULT_GITHUB_REPO, DEFAULT_WORKFLOW_FILE


class CloudDispatcher:
    """Prepares clip specifications and triggers GitHub Actions cloud rendering."""

    def __init__(
        self,
        repo: str = DEFAULT_GITHUB_REPO,
        workflow: str = DEFAULT_WORKFLOW_FILE,
    ):
        self.repo = repo
        self.workflow = workflow

    def generate_clip_spec(
        self,
        video_url: str,
        start_time: float,
        end_time: float,
        title: str,
        game_name: str = "Detroit: Become Human",
        aspect_ratio: str = "square",
        enable_subtitles: bool = True,
        upload_to_youtube: bool = False,
    ) -> Dict[str, Any]:
        """Creates a standardized JSON specification for the cloud rendering job."""
        duration = round(end_time - start_time, 2)
        return {
            "video_url": video_url,
            "start_time": f"{start_time:.2f}",
            "end_time": f"{end_time:.2f}",
            "duration": duration,
            "title": title,
            "game_name": game_name,
            "aspect_ratio": aspect_ratio,
            "enable_subtitles": enable_subtitles,
            "upload_to_youtube": upload_to_youtube,
        }

    def get_dispatch_command(self, clip_spec: Dict[str, Any]) -> str:
        """Constructs the gh workflow run command string."""
        cmd_parts = [
            "gh workflow run", self.workflow,
            f"--repo {self.repo}",
            f'-f video_url="{clip_spec["video_url"]}"',
            f'-f start_time="{clip_spec["start_time"]}"',
            f'-f end_time="{clip_spec["end_time"]}"',
            f'-f title="{clip_spec["title"]}"',
            f'-f game_name="{clip_spec["game_name"]}"',
            f'-f aspect_ratio="{clip_spec["aspect_ratio"]}"',
            f'-f enable_subtitles="{str(clip_spec["enable_subtitles"]).lower()}"',
            f'-f upload_to_youtube="{str(clip_spec["upload_to_youtube"]).lower()}"',
        ]
        return " \\\n  ".join(cmd_parts)

    def dispatch(
        self, clip_spec: Dict[str, Any], dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Dispatches workflow run or returns preview command for dry-run verification.
        """
        cmd_str = self.get_dispatch_command(clip_spec)

        if dry_run:
            return {
                "status": "ready",
                "mode": "dry_run",
                "command": cmd_str,
                "clip_spec": clip_spec,
            }

        cmd = [
            "gh", "workflow", "run", self.workflow,
            "--repo", self.repo,
            "-f", f"video_url={clip_spec['video_url']}",
            "-f", f"start_time={clip_spec['start_time']}",
            "-f", f"end_time={clip_spec['end_time']}",
            "-f", f"title={clip_spec['title']}",
            "-f", f"game_name={clip_spec['game_name']}",
            "-f", f"aspect_ratio={clip_spec['aspect_ratio']}",
            "-f", f"enable_subtitles={str(clip_spec['enable_subtitles']).lower()}",
            "-f", f"upload_to_youtube={str(clip_spec['upload_to_youtube']).lower()}",
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return {
            "status": "dispatched",
            "mode": "cloud_live",
            "command": cmd_str,
            "stdout": res.stdout.strip(),
            "clip_spec": clip_spec,
        }
