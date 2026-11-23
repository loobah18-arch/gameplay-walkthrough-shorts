# 🎮 Gameplay Walkthrough Shorts Clipper

> Turn long-form 4K gameplay walkthroughs and game movie cutscenes into high-retention, cinematic YouTube Shorts like [SaisenGames' Detroit Connor Short](https://youtube.com/shorts/kepvkxTGqVM).

Built with a **zero-phone-load architecture**: all metadata inspection and dialogue scoring run surgically on lightweight environments (e.g. Termux on Android), while heavy multi-gigabyte video slicing, 60fps rendering, and ASS subtitle burning are fully offloaded to GitHub Actions cloud runners.

---

## 🌟 Key Features

- **Cinematic 1:1 Square & 9:16 Layouts**:
  - `square` (1080x1080 / 2160x2160): Exactly matches SaisenGames reference layout — center-crops widescreen cutscenes into high-resolution square framing focusing on dramatic character faces and action.
  - `vertical_crop` (1080x1920): Direct 9:16 vertical crop.
  - `vertical_blurred` (1080x1920): Centered gameplay with blurred background letterboxing.
- **YouTube Cookies & Anti-Bot Defense**:
  - Accepts Netscape cookies or Base64 encoded secrets (`YOUTUBE_COOKIES`).
  - GitHub Actions runs `brainicism/bgutil-ytdlp-pot-provider` container service to generate Proof-of-Origin (PO) tokens, bypassing YouTube HTTP 403 Forbidden errors.
- **Targeted Slicing (`--download-sections`)**:
  - Never downloads multi-hour 50GB walkthrough videos. It downloads **only** the requested 30–60 second cutscene window.
- **Dynamic Dialogue Tension Analyzer**:
  - Scans subtitle transcripts to detect emotional dialogue (keywords like `machine`, `living being`, `deviant`, `betray`, `sacrifice`, `alive`, `choice`).
- **High-Retention ASS Subtitles**:
  - Generates ASS subtitles with centered bold typography, drop shadows, and automatic gold keyword highlights.
- **Broadcast Audio Loudnorm**:
  - Masters game dialogue and sound effects to YouTube Shorts EBU R128 standard (-14 LUFS, -1.5 dB True Peak).

---

## 🏗️ Architecture

```
                                  [ Lightweight Client (Termux Phone) ]
                                    │
                                    ├──> python3 cli.py analyze <url> (Extracts text cues only)
                                    └──> python3 cli.py dispatch <url> --start ... --end ...
                                                │
                                                ▼ (Dispatches via gh workflow run)
[ Cloud Runner (GitHub Actions ubuntu-latest) ]
  ├── 🍪 Decode YOUTUBE_COOKIES secret -> cookies.txt
  ├── 🛡️ Connect to bgutil PO token service (port 4416)
  ├── 📥 yt-dlp --download-sections "*START-END" (Downloads ONLY 45s clip)
  ├── 📝 Generate stylized ASS subtitles
  ├── 🎬 FFmpeg render (1:1 Square / 9:16 Vertical + EBU R128 audio)
  └── 📦 Export Short as downloadable artifact & optional YouTube upload
```

---

## 🍪 Setting Up YouTube Cookies

Long gameplay walkthroughs and 4K cutscenes often trigger YouTube bot detection when downloaded from cloud servers. Configuring cookies ensures 100% reliable fetching:

1. Install the browser extension **"Get cookies.txt LOCALLY"** (Chrome / Firefox / Brave).
2. Log in to [YouTube](https://www.youtube.com).
3. Open the extension while on YouTube and click **"Export"** to save `cookies.txt`.
4. Validate your cookies locally:
   ```bash
   python3 cli.py validate-cookies --file cookies.txt
   ```
5. Add the cookies to your GitHub Repository Secrets:
   - Go to your repository on GitHub: `Settings` → `Secrets and variables` → `Actions`.
   - Click **New repository secret**.
   - **Name**: `YOUTUBE_COOKIES`
   - **Value**: Paste the raw contents of `cookies.txt` (or base64 encode it: `base64 -w 0 cookies.txt`).

---

## 🚀 Quickstart & Usage

### 1. Inspect Walkthrough Metadata
Check title, duration, 60fps support, and story chapters without downloading:
```bash
python3 cli.py fetch-info "https://www.youtube.com/watch?v=WALKTHROUGH_ID"
```

### 2. Discover Viral Cutscene Moments
Automatically scan the transcript for high-tension dialogue and get recommended clip timestamps:
```bash
python3 cli.py analyze "https://www.youtube.com/watch?v=WALKTHROUGH_ID" \
  --game "Detroit: Become Human" \
  --aspect-ratio square
```

### 3. Dispatch Cloud Render
Send the job to GitHub Actions to render in the cloud:
```bash
# Preview command first (dry-run):
python3 cli.py dispatch "https://www.youtube.com/watch?v=WALKTHROUGH_ID" \
  --start 1240 \
  --end 1295 \
  --title "Connor: Just a Machine or Living Being?" \
  --aspect-ratio square \
  --dry-run

# Run live on GitHub Actions:
python3 cli.py dispatch "https://www.youtube.com/watch?v=WALKTHROUGH_ID" \
  --start 1240 \
  --end 1295 \
  --title "Connor: Just a Machine or Living Being?" \
  --aspect-ratio square
```

### 4. Trigger Directly from GitHub Actions Web UI
You can also manually trigger the pipeline directly from GitHub:
1. Go to the **Actions** tab on GitHub.
2. Select **Render Gameplay Walkthrough Short**.
3. Click **Run workflow**, paste the YouTube URL, start/end timestamps, and select `square` (1:1) or `vertical_crop` (9:16).
4. Download the completed `.mp4` file from the **Artifacts** section of the run.

---

## 🧪 Running Unit Tests

Run the full automated test suite:
```bash
python3 -m unittest discover -s tests -v
```

All 20 unit tests verify cookie parsing, VTT decoding, cutscene tension scoring, ASS subtitle formatting, and FFmpeg command generation.

---

## 📜 License
MIT License.
