#!/usr/bin/env python3
"""
Gameplay Walkthrough Shorts Clipper CLI.
Allows discovering cutscenes, analyzing dialogue moments, validating cookies,
and orchestrating cloud renders on GitHub Actions.
"""
import argparse
import hashlib
import math
import os
import re
import sys
from typing import Optional

from config.settings import ASPECT_RATIOS, DEFAULT_ASPECT_RATIO, OUTPUT_DIR, TEMP_DIR
from core.cloud_dispatcher import CloudDispatcher
from core.cookie_manager import CookieManager
from core.cutscene_analyzer import CutsceneAnalyzer
from core.payoff_detector import ActualPayoffDetector
from core.question_manager import QuestionManager
from core.subtitle_builder import SubtitleBuilder
from core.video_renderer import VideoRenderer
from core.walkthrough_crawler import WalkthroughCrawler
from core.walkthrough_fetcher import WalkthroughFetcher
from core.youtube_uploader import YouTubeUploader


def parse_timestamp_arg(raw: str) -> float:
    """Parses float seconds or [HH:]MM:SS[.mmm] into non-negative float seconds."""
    text = str(raw).strip()
    if not text:
        raise argparse.ArgumentTypeError("Empty timestamp value")

    if ":" in text:
        parts = text.split(":")
        if len(parts) not in (2, 3):
            raise argparse.ArgumentTypeError(f"Invalid timestamp format: {raw}")
        try:
            nums = [float(p) for p in parts]
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid timestamp format: {raw}") from exc
        if any(not math.isfinite(n) or n < 0 for n in nums):
            raise argparse.ArgumentTypeError(f"Negative or non-finite timestamp not allowed: {raw}")
        if len(nums) == 2:
            val = nums[0] * 60.0 + nums[1]
        else:
            val = nums[0] * 3600.0 + nums[1] * 60.0 + nums[2]
        return val

    try:
        val = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid timestamp value: {raw}") from exc
    if not math.isfinite(val) or val < 0:
        raise argparse.ArgumentTypeError(f"Timestamp must be finite and >= 0 (got {raw})")
    return val


def _extract_video_key(video_url: str) -> str:
    """Extracts deterministic short video identifier for cache/staging isolation."""
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{6,15})", video_url or "")
    if m:
        return m.group(1)
    return hashlib.sha1((video_url or "").encode("utf-8")).hexdigest()[:10]


def cmd_validate_cookies(args):
    """Validates YouTube cookies from file, environment variable, or base64 argument."""
    data = ""
    if args.file:
        if not os.path.isfile(args.file):
            print(f"❌ Error: Cookie file not found: {args.file}")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            data = f.read()
    elif args.secret is not None:
        data = args.secret
    else:
        env_val = os.environ.get("YOUTUBE_COOKIES", "")
        if env_val:
            data = env_val
        elif os.path.isfile("cookies.txt"):
            with open("cookies.txt", "r", encoding="utf-8") as f:
                data = f.read()
        elif os.path.isfile("youtube_cookies.txt"):
            with open("youtube_cookies.txt", "r", encoding="utf-8") as f:
                data = f.read()

    if not data or not data.strip():
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
    print(f"Total Lines: {info.get('total_lines', 0)}")
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
        dur = int(info.get("duration") or 0)
        print("\n========================================")
        print(f"🎬 Title: {info.get('title') or 'Unknown'}")
        print(f"📺 Channel: {info.get('channel') or 'Unknown'}")
        print(f"⏱️ Duration: {dur}s ({dur // 60} mins)")
        print(f"🌟 Max Resolution: {info.get('max_resolution') or 'Unknown'}")
        print(f"🎮 60 FPS Support: {'Yes' if info.get('has_60fps') else 'No'}")
        print(f"📑 Chapters Count: {len(info.get('chapters') or [])}")
        print("========================================")
        if info.get("chapters"):
            print("Top Chapters:")
            for c in info["chapters"][:5]:
                c_start = c.get("start_time")
                start_label = int(c_start) if c_start is not None else 0
                print(f"  - [{start_label}s] {c.get('title')}")
    except Exception as e:
        print(f"❌ Failed to fetch video info: {e}")
        sys.exit(1)


def cmd_analyze(args):
    """Downloads transcript (zero video bytes) and identifies top dramatic cutscene moments with payoffs."""
    fetcher = WalkthroughFetcher()
    analyzer = CutsceneAnalyzer()

    print(f"🔍 Fetching video info and transcript for: {args.url}")
    info = fetcher.fetch_video_info(args.url, cookies_path=args.cookies, proxy=args.proxy)
    video_id = info.get("id") or _extract_video_key(args.url)

    print("📥 Extracting dialogue cues from subtitles...")
    cues = fetcher.fetch_transcript(args.url, video_id=video_id, cookies_path=args.cookies, proxy=args.proxy)

    if not cues:
        print("⚠️ No subtitles found for this video. Analyzing chapters for physical action climaxes & payoffs...")
        chapters = info.get("chapters") or []
        if not chapters:
            print("❌ No subtitles or chapters found. Provide manual --start and --end timestamps to dispatch.")
            sys.exit(0)

        dramatic_chapter_keywords = [
            "climax", "resolution", "choice", "consequences", "test", "interrogation",
            "hostage", "rescue", "murder", "chase", "confrontation", "conversation",
            "fight", "standoff", "decision", "truth", "alive",
        ]

        scored_chapters = []
        for chap in chapters:
            c_start = chap.get("start_time")
            c_end = chap.get("end_time")
            if c_start is None or c_end is None:
                continue

            dur = c_end - c_start
            if dur < 25:
                continue

            title = chap.get("title") or "Cutscene Chapter"
            title_lower = title.lower()
            score = 5.0
            for kw in dramatic_chapter_keywords:
                if kw in title_lower:
                    score += 5.0

            window = ActualPayoffDetector.calculate_chapter_payoff_window(
                chapter_start=c_start,
                chapter_end=c_end,
                target_duration=55.0,
            )
            scored_chapters.append({
                "title": title,
                "score": score,
                "chapter_dur": dur,
                "window": window,
            })

        scored_chapters.sort(key=lambda x: x["score"], reverse=True)

        if not scored_chapters:
            print("❌ No eligible chapters >= 25s found. Provide manual --start and --end timestamps.")
            sys.exit(0)

        print("\n=======================================================")
        print(f"🎬 Top {min(5, len(scored_chapters))} Action Climax Chapters Found (Payoff-First Alignment):")
        print("=======================================================")
        for idx, item in enumerate(scored_chapters[:5], 1):
            w = item["window"]
            short_title = f"{item['title']} - Climax | {args.game}"
            print(f"\n#{idx} [Action Score: {item['score']}] Chapter: \"{item['title']}\"")
            print(f"   🎯 Payoff Window: {w['start']}s -> {w['end']}s ({w['duration']}s)")
            print(f"   Arc Phase: {w['arc_phase']} (Anchored to final action resolution)")
            print(f"   Proposed Title: \"{short_title}\"")

        top_w = scored_chapters[0]["window"]
        top_title = f"{scored_chapters[0]['title']} - Climax | {args.game}"
        print("\n💡 Recommended Cloud Dispatch Command (Anchored to Actual Payoff):")
        dispatcher = CloudDispatcher(repo=args.repo)
        spec = dispatcher.generate_clip_spec(
            video_url=args.url,
            start_time=top_w["start"],
            end_time=top_w["end"],
            title=top_title,
            game_name=args.game,
            aspect_ratio=args.aspect_ratio,
        )
        print(dispatcher.get_dispatch_command(spec))
        return

    require_payoff = not getattr(args, "allow_open_ended", False)
    print(f"✅ Found {len(cues)} dialogue cues. Scoring dramatic tension & payoffs (require_payoff={require_payoff})...")
    segments = analyzer.find_viral_segments(
        cues,
        min_duration=args.min_dur,
        max_duration=args.max_dur,
        require_payoff=require_payoff,
    )

    if not segments:
        print("⚠️ No cutscene segments met strict payoff criteria. Re-run with --allow-open-ended to inspect open-ended candidates.")
        sys.exit(0)

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
    try:
        spec = dispatcher.generate_clip_spec(
            video_url=args.url,
            start_time=args.start,
            end_time=args.end,
            title=args.title,
            game_name=args.game,
            aspect_ratio=args.aspect_ratio,
            enable_subtitles=not args.no_subs,
            upload_to_youtube=args.upload,
        )
    except ValueError as e:
        print(f"❌ Invalid time range: {e}")
        sys.exit(1)

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
    if end_time <= start_time:
        print(f"❌ Invalid clip range: end ({end_time}) must be > start ({start_time})")
        sys.exit(1)

    video_url = args.url
    vid_key = _extract_video_key(video_url)
    clip_duration = end_time - start_time

    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    temp_stem = os.path.join(TEMP_DIR, f"raw_clip_{vid_key}_{int(start_time)}_{int(end_time)}")
    temp_raw = f"{temp_stem}.mp4"
    ass_path: Optional[str] = os.path.join(TEMP_DIR, f"subs_{vid_key}_{int(start_time)}_{int(end_time)}.ass")

    raw_output_name = os.path.basename(args.output) if args.output else f"short_{vid_key}_{int(start_time)}_{args.aspect_ratio}.mp4"
    if not raw_output_name.lower().endswith(".mp4"):
        raw_output_name += ".mp4"
    output_filename = re.sub(r"[^A-Za-z0-9._-]", "_", raw_output_name)

    # 1. Check if raw clip exists locally in temp/, otherwise download via yt-dlp
    actual_raw = VideoRenderer.find_existing_media_file(temp_raw)
    if not actual_raw:
        print(f"📥 Downloading section {start_time}s to {end_time}s for {vid_key}...")
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

    # 2. Extract transcript and generate ASS subtitles with AniDoc top question
    top_question = getattr(args, "top_question", None)
    game_name = getattr(args, "game", "Epic Game Cutscene")
    if not top_question:
        qm = QuestionManager()
        game_slug = re.sub(r"[^a-zA-Z0-9]+", "_", game_name.lower())
        top_question = qm.generate_question(game_key=game_slug, game_name=game_name, cutscene_title=raw_output_name)

    words_to_burn = []
    if args.enable_subtitles:
        try:
            print("🎙️ Transcribing cutscene audio for frame-accurate word-level subtitles...")
            words_to_burn = SubtitleBuilder.transcribe_audio_words(actual_raw, temp_dir=TEMP_DIR)
            if words_to_burn:
                print(f"✅ Transcribed {len(words_to_burn)} words directly from cutscene audio.")
        except Exception as e_w:
            print(f"⚠️ Audio transcription notice ({e_w}); checking VTT fallback...")

        if not words_to_burn:
            try:
                print("📝 Fetching transcript fallback cues...")
                fetcher = WalkthroughFetcher()
                cues = fetcher.fetch_transcript(video_url, video_id=vid_key, cookies_path=args.cookies, proxy=args.proxy)
                cues_to_burn = [c for c in cues if c["end"] > start_time and c["start"] < end_time]
                words_to_burn = SubtitleBuilder.cues_to_words(cues_to_burn, time_offset=start_time)
            except Exception as e:
                print(f"⚠️ Subtitle generation error ({e}); rendering without burned dialogue.")

    if words_to_burn or top_question:
        SubtitleBuilder.generate_anidoc_ass(
            words=words_to_burn,
            output_path=ass_path,
            aspect_ratio_key=args.aspect_ratio,
            max_duration=clip_duration,
            top_question=top_question,
        )
        print(f"✅ Generated AniDoc-style ASS with top engaging question at {ass_path}")
    else:
        ass_path = None

    # 3. Inspect audio payoff peak/drop telemetry safely
    audio_events = ActualPayoffDetector.detect_audio_climax(actual_raw, start_offset=start_time)
    if audio_events:
        top_ev = audio_events[0]
        print(f"🎯 Top audio beat detected: {top_ev['type']} at {top_ev['timestamp']}s (peak={top_ev.get('pre_peak_db')}dB)")

    # 4. Render final output with FFmpeg
    print(f"🎥 Rendering final Short (Aspect Ratio: {args.aspect_ratio})...")
    renderer = VideoRenderer(output_dir=OUTPUT_DIR, temp_dir=TEMP_DIR)
    final_path = renderer.render_short(
        raw_video_path=actual_raw,
        output_filename=output_filename,
        aspect_ratio=args.aspect_ratio,
        ass_subtitle_path=ass_path,
    )
    print(f"🎉 Short successfully rendered: {final_path}")

    # 5. Persist to upload history and publish only when --upload is enabled
    uploader = YouTubeUploader()
    if getattr(args, "upload", False):
        uploader.publish_short(
            video_path=final_path,
            title=getattr(args, "title", raw_output_name),
            game_name=game_name,
            source_video_id=vid_key,
            cutscene_title=raw_output_name,
            top_question=top_question or "",
            duration=clip_duration,
        )
    else:
        print("ℹ️ YouTube upload disabled (--no-upload). Artifact saved only.")
        uploader.record_upload(
            video_file=final_path,
            title=getattr(args, "title", raw_output_name),
            game_name=game_name,
            source_video_id=vid_key,
            cutscene_title=raw_output_name,
            top_question=top_question or "",
            published=False,
            duration=clip_duration,
        )


def _select_verified_cutscene(candidate, fetcher, analyzer, crawler, cookies_path=None, proxy=None):
    """
    Validates that a walkthrough candidate is >= 180s and contains either a verified
    cutscene chapter or dense cutscene dialogue with a real payoff climax.
    Returns None instead of guessing an arbitrary timestamp window.
    """
    vid_url = candidate["url"]
    vid_id = candidate["video_id"]
    game_name = candidate["game_name"]

    try:
        info = fetcher.fetch_video_info(vid_url, cookies_path=cookies_path, proxy=proxy)
    except Exception as e:
        print(f"⚠️ Could not fetch metadata for '{candidate['title']}' ({vid_id}): {e}")
        info = {}

    duration = info.get("duration") or candidate.get("duration") or 0
    age_limit = info.get("age_limit") or candidate.get("age_limit") or 0
    chapters = info.get("chapters") or candidate.get("chapters") or []

    print(f"  ℹ️ [Candidate Stats] dur={duration}s, age_limit={age_limit}, chapters={len(chapters)}")

    if duration and duration < 180:
        print(f"⏭️ Rejecting '{candidate['title']}' ({vid_id}): duration {duration}s < 180s (Short/too short).")
        return None

    if duration and duration > 28800:
        print(f"⏭️ Rejecting '{candidate['title']}' ({vid_id}): duration {duration}s > 8 hours (oversized movie).", flush=True)
        return None

    if age_limit >= 18:
        print(f"⏭️ Rejecting '{candidate['title']}' ({vid_id}): age-restricted (age_limit={age_limit}).")
        return None
    eligible_chapters = []
    for chap in chapters:
        c_title = chap.get("title", "")
        affinity = CutsceneAnalyzer.score_chapter_cutscene_affinity(c_title)
        if affinity < 0:
            continue
        dur = (chap.get("end_time") or 0) - (chap.get("start_time") or 0)
        if dur >= 25 and not crawler.is_previously_clipped(vid_id, c_title):
            eligible_chapters.append((chap, affinity))

    if eligible_chapters:
        eligible_chapters.sort(key=lambda x: x[1], reverse=True)
        best_chap, _ = eligible_chapters[0]
        window = ActualPayoffDetector.calculate_chapter_payoff_window(
            chapter_start=best_chap["start_time"],
            chapter_end=best_chap["end_time"],
            target_duration=55.0,
        )
        scene_title = best_chap.get("title", candidate["title"])
        print(f"🎬 Selected Cutscene Chapter: '{scene_title}' ({window['start']}s -> {window['end']}s)")
        return {"start": window["start"], "end": window["end"], "scene_title": scene_title}

    try:
        cues = fetcher.fetch_transcript(vid_url, video_id=vid_id, cookies_path=cookies_path, proxy=proxy)
    except Exception as exc:
        print(f"⏭️ Rejecting '{candidate['title']}' ({vid_id}): no chapters and transcript unavailable ({exc}).")
        return None

    segments = analyzer.find_viral_segments(cues, min_duration=25, max_duration=58, require_payoff=True)
    for seg in segments:
        scene_title = analyzer.generate_short_title(
            game_name, seg["sample_dialogue"], payoff_phrase=seg.get("payoff_line")
        )
        if not crawler.is_previously_clipped(vid_id, scene_title):
            print(f"🎬 Selected Dialogue Cutscene Climax: '{scene_title}' ({seg['start']}s -> {seg['end']}s)", flush=True)
            return {"start": seg["start"], "end": seg["end"], "scene_title": scene_title}

    print(f"⏭️ Rejecting '{candidate['title']}' ({vid_id}): no verified cutscene chapters or payoff dialogue found (cues={len(cues)}, segs={len(segments)}).", flush=True)
    return None


def cmd_daily_job(args):
    """Autonomous 24-hour cloud runner entrypoint."""
    from core.preflight_gate import check_preflight_gate
    if not check_preflight_gate() and not getattr(args, "force", False):
        print("⏸️ 24h pre-flight gate not satisfied. Exiting daily job.")
        sys.exit(0)

    crawler = WalkthroughCrawler()
    games_dict = crawler.catalog.get("games", {})
    all_game_keys = list(games_dict.keys())
    if not all_game_keys:
        raise RuntimeError("No games found in catalog.")

    if args.game and args.game in games_dict:
        target_game_keys = [args.game] + [g for g in all_game_keys if g != args.game]
    else:
        history = crawler.get_clipped_history()
        idx = len(history.get("entries", [])) % len(all_game_keys)
        target_game_keys = [all_game_keys[idx]] + [g for i, g in enumerate(all_game_keys) if i != idx]

    fetcher = WalkthroughFetcher()
    analyzer = CutsceneAnalyzer()
    qm = QuestionManager()

    rendered_successfully = False

    for g_key in target_game_keys:
        candidates = crawler.list_candidates(
            preferred_game=g_key,
            proxy=args.proxy,
            cookies_path=args.cookies,
            max_candidates=12,
        )
        if not candidates:
            continue

        for candidate in candidates:
            print(f"🎯 Inspecting Candidate: {candidate['title']} ({candidate['url']})")
            picked = _select_verified_cutscene(
                candidate=candidate,
                fetcher=fetcher,
                analyzer=analyzer,
                crawler=crawler,
                cookies_path=args.cookies,
                proxy=args.proxy,
            )
            if not picked:
                continue

            vid_url = candidate["url"]
            game_name = candidate["game_name"]
            start_sec = picked["start"]
            end_sec = picked["end"]
            scene_title = picked["scene_title"]

            top_question = qm.generate_question(
                game_key=candidate.get("game_key", g_key),
                game_name=game_name,
                cutscene_title=scene_title,
            )
            print(f"💡 Top Engaging Question: \"{top_question}\"")

            render_args = argparse.Namespace(
                url=vid_url,
                start=start_sec,
                end=end_sec,
                aspect_ratio="vertical_letterbox",
                enable_subtitles=True,
                cookies=args.cookies,
                proxy=args.proxy,
                po_token=getattr(args, "po_token", None),
                visitor_data=getattr(args, "visitor_data", None),
                output=f"{re.sub(r'[^A-Za-z0-9]+', '_', scene_title)[:40]}_letterbox.mp4",
                top_question=top_question,
                game=game_name,
                title=f"{scene_title} | {game_name}",
                upload=getattr(args, "upload", False),
            )

            try:
                cmd_render_cloud_job(render_args)
                rendered_successfully = True
                break
            except Exception as e:
                print(f"⚠️ Render failed for '{candidate['title']}': {e}. Trying next candidate...")

        if rendered_successfully:
            break

    if not rendered_successfully:
        print("❌ Could not successfully cut, render, and publish any candidate walkthrough. Aborting.")
        sys.exit(1)


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
    p_disp.add_argument("--start", required=True, type=parse_timestamp_arg, help="Start time in seconds or HH:MM:SS")
    p_disp.add_argument("--end", required=True, type=parse_timestamp_arg, help="End time in seconds or HH:MM:SS")
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
    p_cloud.add_argument("--start", required=True, type=parse_timestamp_arg, help="Start time in seconds or HH:MM:SS")
    p_cloud.add_argument("--end", required=True, type=parse_timestamp_arg, help="End time in seconds or HH:MM:SS")
    p_cloud.add_argument("--aspect-ratio", default=DEFAULT_ASPECT_RATIO, choices=list(ASPECT_RATIOS.keys()))
    p_cloud.add_argument("--enable-subtitles", action="store_true", default=False, help="Burn styled ASS subtitles")
    p_cloud.add_argument("--no-subtitles", dest="enable_subtitles", action="store_false", help="Disable ASS subtitles")
    p_cloud.add_argument("--top-question", help="AniDoc-style top engaging question header")
    p_cloud.add_argument("--game", default="Epic Game Cutscene", help="Game Name")
    p_cloud.add_argument("--title", help="Cutscene Short title")
    p_cloud.add_argument("--cookies", help="Path to cookies.txt")
    p_cloud.add_argument("--proxy", help="HTTP/HTTPS/SOCKS5 proxy URL")
    p_cloud.add_argument("--po-token", help="YouTube PO Token")
    p_cloud.add_argument("--visitor-data", help="YouTube Visitor Data")
    p_cloud.add_argument("--output", help="Output filename")
    p_cloud.add_argument("--upload", action="store_true", default=False, help="Upload rendered Short to YouTube")
    p_cloud.add_argument("--no-upload", dest="upload", action="store_false", help="Skip YouTube upload")
    p_cloud.set_defaults(func=cmd_render_cloud_job)

    # daily-job (autonomous 24-hour pipeline)
    p_daily = subparsers.add_parser("daily-job", help="Autonomous 24-hour walkthrough cutscene clipper")
    p_daily.add_argument("--game", help="Optional game override (default: auto-rotate catalog)")
    p_daily.add_argument("--force", action="store_true", help="Bypass 24h pre-flight gate check")
    p_daily.add_argument("--upload", action="store_true", default=True, help="Upload rendered Short to YouTube (default: True)")
    p_daily.add_argument("--no-upload", dest="upload", action="store_false", help="Skip YouTube upload")
    p_daily.add_argument("--cookies", help="Path to cookies.txt")
    p_daily.add_argument("--proxy", help="HTTP/HTTPS/SOCKS5 proxy URL")
    p_daily.add_argument("--po-token", help="YouTube PO Token")
    p_daily.add_argument("--visitor-data", help="YouTube Visitor Data")
    p_daily.set_defaults(func=cmd_daily_job)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
