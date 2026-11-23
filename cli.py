#!/usr/bin/env python3
"""
Gameplay Walkthrough Shorts Clipper CLI.
Allows discovering cutscenes, analyzing dialogue moments, validating cookies,
and orchestrating cloud renders on GitHub Actions.
"""
import sys
import os
import shutil
import argparse
import json
from typing import Optional

from config.settings import DEFAULT_ASPECT_RATIO, ASPECT_RATIOS
from core.cookie_manager import CookieManager
from core.walkthrough_fetcher import WalkthroughFetcher
from core.cutscene_analyzer import CutsceneAnalyzer
from core.subtitle_builder import SubtitleBuilder
from core.video_renderer import VideoRenderer
from core.cloud_dispatcher import CloudDispatcher


def cmd_validate_cookies(args):
    """Validates YouTube cookies from file, environment variable, or base64 argument."""
    data = ""
    if args.file and os.path.isfile(args.file):
        with open(args.file, "r", encoding="utf-8") as f:
            data = f.read()
    elif args.secret:
        data = args.secret
    else:
        # Check standard env var or files
        env_val = os.environ.get("YOUTUBE_COOKIES", "")
        if env_val:
            data = env_val
        elif os.path.isfile("cookies.txt"):
            with open("cookies.txt", "r", encoding="utf-8") as f:
                data = f.read()
        elif os.path.isfile("youtube_cookies.txt"):
            with open("youtube_cookies.txt", "r", encoding="utf-8") as f:
                data = f.read()

    if not data:
        print("❌ Error: No cookie data found. Provide a file with --file, raw string with --secret, or set YOUTUBE_COOKIES.")
        sys.exit(1)

    decoded = CookieManager.decode_cookie_data(data)
    info = CookieManager.validate_cookies_content(decoded)

    print("========================================")
    print("🍪 YouTube Cookies Validation Report")
    print("========================================")
    print(f"Status: {'✅ Valid' if info['valid'] else '⚠️ Invalid or Incomplete'}")
    print(f"Includes YouTube Domain: {'Yes' if info['has_youtube'] else 'No'}")
    print(f"Critical Auth Tokens Found: {', '.join(info['critical_found']) or 'None'}")
    print(f"Expired Cookies Detected: {info['expired_count']}")
    print(f"Total Lines: {info['total_lines']}")
    print(f"Message: {info['message']}")
    print("========================================")

    if args.export:
        CookieManager.export_cookie_file(decoded, args.export)
        print(f"📁 Successfully exported cookies to {args.export} (chmod 600)")


def cmd_fetch_info(args):
    """Retrieves walkthrough video metadata and available qualities without downloading video."""
    fetcher = WalkthroughFetcher()
    print(f"🔍 Fetching metadata for: {args.url}")
    try:
        info = fetcher.fetch_video_info(args.url, cookies_path=args.cookies, proxy=args.proxy)
        print("\n========================================")
        print(f"🎬 Title: {info['title']}")
        print(f"📺 Channel: {info['channel']}")
        print(f"⏱️ Duration: {info['duration']}s ({info['duration']//60} mins)")
        print(f"🌟 Max Resolution: {info['max_resolution']}")
        print(f"🎮 60 FPS Support: {'Yes' if info['has_60fps'] else 'No'}")
        print(f"📑 Chapters Count: {len(info['chapters'])}")
        print("========================================")
        if info['chapters']:
            print("Top Chapters:")
            for c in info['chapters'][:5]:
                print(f"  - [{int(c.get('start_time', 0))}s] {c.get('title')}")
    except Exception as e:
        print(f"❌ Failed to fetch video info: {e}")
        sys.exit(1)


def cmd_analyze(args):
    """Downloads transcript (zero video bytes) and identifies top dramatic cutscene moments with payoffs."""
    fetcher = WalkthroughFetcher()
    analyzer = CutsceneAnalyzer()

    print(f"🔍 Fetching video info and transcript for: {args.url}")
    info = fetcher.fetch_video_info(args.url, cookies_path=args.cookies, proxy=args.proxy)
    video_id = info["id"]

    print("📥 Extracting dialogue cues from subtitles...")
    cues = fetcher.fetch_transcript(args.url, video_id=video_id, cookies_path=args.cookies, proxy=args.proxy)

    if not cues:
        print("⚠️ No subtitles found for this video. You can still manually clip using --start and --end timestamps.")
        sys.exit(0)

    require_payoff = not getattr(args, "allow_open_ended", False)
    print(f"✅ Found {len(cues)} dialogue cues. Scoring dramatic tension & payoffs (require_payoff={require_payoff})...")
    segments = analyzer.find_viral_segments(
        cues,
        min_duration=args.min_dur,
        max_duration=args.max_dur,
        require_payoff=require_payoff,
    )

    print("\n=======================================================")
    print(f"🔥 Top {len(segments)} Dramatic Cutscene Moments Found:")
    print("=======================================================")
    for idx, seg in enumerate(segments, 1):
        title = analyzer.generate_short_title(
            args.game,
            seg["sample_dialogue"].split("|")[0],
            payoff_phrase=seg.get("payoff_line"),
        )
        print(f"\n#{idx} [Score: {seg['score']}]  {seg['start']}s -> {seg['end']}s ({seg['duration']}s)")
        print(f"   Proposed Title: \"{title}\"")
        print(f"   🎯 Payoff [{seg.get('payoff_type', 'none')}]: \"{seg.get('payoff_line', '')}\" (Beat: {seg.get('pause_after', 0)}s, Score: {seg.get('payoff_score', 0)})")
        print(f"   Dialogue: \"{seg['sample_dialogue']}\"")

    if segments:
        top = segments[0]
        print("\n💡 Recommended Cloud Dispatch Command:")
        dispatcher = CloudDispatcher(repo=args.repo)
        title = analyzer.generate_short_title(
            args.game,
            top["sample_dialogue"].split("|")[0],
            payoff_phrase=top.get("payoff_line"),
        )
        spec = dispatcher.generate_clip_spec(
            video_url=args.url,
            start_time=top["start"],
            end_time=top["end"],
            title=title,
            game_name=args.game,
            aspect_ratio=args.aspect_ratio,
        )
        print(dispatcher.get_dispatch_command(spec))


def cmd_dispatch(args):
    """Prepares clip spec and dispatches cloud rendering to GitHub Actions."""
    dispatcher = CloudDispatcher(repo=args.repo)
    spec = dispatcher.generate_clip_spec(
        video_url=args.url,
        start_time=float(args.start),
        end_time=float(args.end),
        title=args.title,
        game_name=args.game,
        aspect_ratio=args.aspect_ratio,
        enable_subtitles=not args.no_subs,
        upload_to_youtube=args.upload,
    )

    result = dispatcher.dispatch(spec, dry_run=args.dry_run)
    if args.dry_run:
        print("🚀 [Dry-Run] Cloud Dispatch Command Ready:")
        print(result["command"])
    else:
        print(f"✅ Dispatched cloud render to {args.repo}! Workflow is running.")


def cmd_render_cloud_job(args):
    """
    Executed inside GitHub Actions CI/CD runner.
    Downloads specific slice using cookies, builds ASS subtitles, and renders final MP4.
    """
    print("🎬 Starting Cloud-Side Render Job...")
    start_time = float(args.start)
    end_time = float(args.end)
    video_url = args.url

    temp_raw = os.path.join("temp", f"raw_clip_{int(start_time)}.mp4")
    ass_path = os.path.join("temp", f"subs_{int(start_time)}.ass")
    output_filename = args.output or f"short_{int(start_time)}_{args.aspect_ratio}.mp4"

    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    # Check for pre-staged asset clip
    for ext in [".webm", ".mp4", ".mkv"]:
        sample_path = os.path.join("assets", "samples", f"raw_clip_{int(start_time)}{ext}")
        if os.path.isfile(sample_path):
            staged_dest = temp_raw + ext
            if not os.path.isfile(staged_dest):
                shutil.copy(sample_path, staged_dest)
            break

    # 1. Check if raw clip was pre-staged, otherwise download via yt-dlp
    actual_raw = VideoRenderer.find_existing_media_file(temp_raw)
    if not actual_raw:
        print(f"📥 Downloading section {start_time}s to {end_time}s...")
        downloaded_path = VideoRenderer.download_video_section(
            video_url=video_url,
            start_time=start_time,
            end_time=end_time,
            output_filepath=temp_raw,
            cookies_path=args.cookies,
            proxy=args.proxy,
            po_token=getattr(args, "po_token", None),
            visitor_data=getattr(args, "visitor_data", None),
        )
        actual_raw = downloaded_path if os.path.isfile(downloaded_path) else temp_raw
        if not os.path.isfile(actual_raw):
            found = VideoRenderer.find_existing_media_file(temp_raw)
            if found:
                actual_raw = found
    else:
        print(f"📦 Pre-staged raw video slice detected: {actual_raw}")

    # 2. Extract transcript and generate ASS subtitles if enabled
    if args.enable_subtitles:
        try:
            print("📝 Generating styled ASS subtitles...")
            fetcher = WalkthroughFetcher()
            cues = fetcher.fetch_transcript(video_url, video_id="current", cookies_path=args.cookies, proxy=args.proxy)
            # Filter cues to this clip's time range
            clip_cues = [c for c in cues if c["start"] >= (start_time - 1.0) and c["end"] <= (end_time + 1.0)]
            if clip_cues:
                SubtitleBuilder.generate_ass(
                    cues=clip_cues,
                    output_path=ass_path,
                    aspect_ratio_key=args.aspect_ratio,
                    time_offset=start_time,
                )
                print(f"✅ Generated ASS subtitles at {ass_path}")
            else:
                print("ℹ️ No subtitle cues found in this time range; rendering without burned subtitles.")
                ass_path = None
        except Exception as e:
            print(f"⚠️ Subtitle generation error ({e}); rendering without burned subtitles.")
            ass_path = None
    else:
        ass_path = None

    # 3. Render final output with FFmpeg
    print(f"🎥 Rendering final Short (Aspect Ratio: {args.aspect_ratio})...")
    renderer = VideoRenderer(output_dir="output", temp_dir="temp")
    final_path = renderer.render_short(
        raw_video_path=actual_raw,
        output_filename=output_filename,
        aspect_ratio=args.aspect_ratio,
        ass_subtitle_path=ass_path,
    )
    print(f"🎉 Short successfully rendered: {final_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Gameplay Walkthrough Shorts Clipper (Termux + GitHub Actions)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # validate-cookies
    p_cookie = subparsers.add_parser("validate-cookies", help="Validate YouTube cookies")
    p_cookie.add_argument("--file", help="Path to cookies.txt file")
    p_cookie.add_argument("--secret", help="Raw or base64 cookie string")
    p_cookie.add_argument("--export", help="Export clean cookies.txt to given path")
    p_cookie.set_defaults(func=cmd_validate_cookies)

    # fetch-info
    p_info = subparsers.add_parser("fetch-info", help="Fetch walkthrough video metadata")
    p_info.add_argument("url", help="YouTube video URL")
    p_info.add_argument("--cookies", help="Path to cookies.txt")
    p_info.add_argument("--proxy", help="HTTP/HTTPS/SOCKS5 proxy URL")
    p_info.set_defaults(func=cmd_fetch_info)

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze cutscene dialogue and find viral clips")
    p_analyze.add_argument("url", help="YouTube video URL")
    p_analyze.add_argument("--game", default="Detroit: Become Human", help="Game title")
    p_analyze.add_argument("--aspect-ratio", default=DEFAULT_ASPECT_RATIO, choices=list(ASPECT_RATIOS.keys()))
    p_analyze.add_argument("--min-dur", type=int, default=25, help="Minimum clip duration in seconds")
    p_analyze.add_argument("--max-dur", type=int, default=58, help="Maximum clip duration in seconds")
    p_analyze.add_argument("--cookies", help="Path to cookies.txt")
    p_analyze.add_argument("--proxy", help="HTTP/HTTPS/SOCKS5 proxy URL")
    p_analyze.add_argument("--repo", default="loobah18-arch/gameplay-walkthrough-shorts", help="GitHub repo")
    p_analyze.add_argument("--allow-open-ended", action="store_true", default=False, help="Allow clips without a decisive payoff/climax")
    p_analyze.set_defaults(func=cmd_analyze)

    # dispatch
    p_disp = subparsers.add_parser("dispatch", help="Dispatch cloud render job to GitHub Actions")
    p_disp.add_argument("url", help="YouTube video URL")
    p_disp.add_argument("--start", required=True, type=float, help="Start time in seconds")
    p_disp.add_argument("--end", required=True, type=float, help="End time in seconds")
    p_disp.add_argument("--title", default="Epic Game Cutscene Moment", help="Short Title")
    p_disp.add_argument("--game", default="Detroit: Become Human", help="Game Name")
    p_disp.add_argument("--aspect-ratio", default=DEFAULT_ASPECT_RATIO, choices=list(ASPECT_RATIOS.keys()))
    p_disp.add_argument("--no-subs", action="store_true", help="Disable burned subtitles")
    p_disp.add_argument("--upload", action="store_true", help="Upload to YouTube Shorts")
    p_disp.add_argument("--dry-run", action="store_true", default=False, help="Print command without running")
    p_disp.add_argument("--repo", default="loobah18-arch/gameplay-walkthrough-shorts", help="Target GitHub repo")
    p_disp.set_defaults(func=cmd_dispatch)

    # render-cloud-job
    p_cloud = subparsers.add_parser("render-cloud-job", help="Internal cloud runner job")
    p_cloud.add_argument("--url", required=True, help="YouTube video URL")
    p_cloud.add_argument("--start", required=True, type=float, help="Start time in seconds")
    p_cloud.add_argument("--end", required=True, type=float, help="End time in seconds")
    p_cloud.add_argument("--aspect-ratio", default="square", choices=list(ASPECT_RATIOS.keys()))
    p_cloud.add_argument("--enable-subtitles", action="store_true", default=True)
    p_cloud.add_argument("--cookies", help="Path to cookies.txt")
    p_cloud.add_argument("--proxy", help="HTTP/HTTPS/SOCKS5 proxy URL")
    p_cloud.add_argument("--po-token", help="YouTube PO Token")
    p_cloud.add_argument("--visitor-data", help="YouTube Visitor Data")
    p_cloud.add_argument("--output", help="Output filename")
    p_cloud.set_defaults(func=cmd_render_cloud_job)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
