"""
Cloud Dispatcher for GitHub Actions CI/CD.
Orchestrates remote server-side rendering so zero heavy media processing runs on the phone.
"""
import subprocess
from typing import Dict, Any
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

    @staticmethod
    def _escape_double_quoted(val: str) -> str:
        """Escapes characters that break or execute inside bash double quotes."""
        return (
            str(val)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("$", "\\$")
            .replace("`", "\\`")
        )

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
        start_val = float(start_time)
        end_val = float(end_time)
        if start_val < 0:
            raise ValueError(f"start_time must be >= 0 (got {start_val})")
        if end_val <= start_val:
            raise ValueError(f"end_time ({end_val}) must be greater than start_time ({start_val})")

        duration = round(end_val - start_val, 2)
        return {
            "video_url": video_url,
            "start_time": f"{start_val:.2f}",
            "end_time": f"{end_val:.2f}",
            "duration": duration,
            "title": title,
            "game_name": game_name,
            "aspect_ratio": aspect_ratio,
            "enable_subtitles": enable_subtitles,
            "upload_to_youtube": upload_to_youtube,
        }

    def get_dispatch_command(self, clip_spec: Dict[str, Any]) -> str:
        """Constructs a shell-safe gh workflow run command string."""
        esc = self._escape_double_quoted
        cmd_parts = [
            "gh workflow run", self.workflow,
            f"--repo {self.repo}",
            f'-f video_url="{esc(clip_spec["video_url"])}"',
            f'-f start_time="{esc(clip_spec["start_time"])}"',
            f'-f end_time="{esc(clip_spec["end_time"])}"',
            f'-f title="{esc(clip_spec["title"])}"',
            f'-f game_name="{esc(clip_spec["game_name"])}"',
            f'-f aspect_ratio="{esc(clip_spec["aspect_ratio"])}"',
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

        if clip_spec.get("upload_to_youtube"):
            print("⚠️ Note: Automatic YouTube upload is not yet wired in the cloud workflow; rendering artifact only.")

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
