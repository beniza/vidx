# VIDX User Guide & Tutorials
> Step-by-step documentation for Bible translation field coordinators and technicians.

---

## 📖 Introduction: The AUDX + VIDX Workflow

When producing multimedia scripture releases, translation teams typically follow a two-stage automated pipeline:
1. **AUDX:** Processes raw studio recordings, validates chapter structures, applies noise reduction/normalization, and outputs standardized audio files (e.g., `SND-MRK-5.mp3`).
2. **VIDX (This Companion Tool):** Takes the finished AUDX audio, combines it with the USFM scripture text and verse timing maps (from Aeneas or Scripture App), and composites broadcast-ready lyric videos with rich subtitles.

```
[Studio Recording] ──► [ AUDX ] ──► Standardized Audio (.mp3) ─┐
                                                             │
[USFM Scripture]   ──► [ Aeneas ] ──► Timing Map (.txt)       ┼─► [ VIDX ] ──► MP4 Video / SRT Subtitles
                                                             │
[Background Media] ──► (Video Loop / Image) ─────────────────┘
```

---

## 🛠️ Step 1: Setting Up Your Workspace Folder Structure

To ensure repeatable, error-free batch conversions across single chapters, full books, or the entire New Testament, we strongly recommend adopting a standardized folder hierarchy in your workspace directory. 

Because VIDX includes an intelligent internal USFM parser, **multiple chapters or even entire New Testaments can share a single USFM source file**, removing the need to split USFM files by chapter!

### Recommended Directory Structure:
```
my_scripture_project/
├── project.yaml              # Main configuration file (copy from our examples/ folder)
│
├── usfm/                     # Scripture text source files
│   └── 42MRKsnd.SFM          # Whole book USFM 3.0 file (or entire NT bundle)
│
├── audio/                    # Standardized studio recordings (produced via AUDX)
│   ├── SND-MRK-01.mp3        # Chapter 1 audio (.mp3, .wav, or .mpeg)
│   ├── SND-MRK-02.mp3        # Chapter 2 audio
│   └── SND-MRK-03.mp3
│
├── timing/                   # Verse-level timing maps (from Aeneas or Scripture App)
│   ├── MRK_01_timing.txt     # Tab-delimited timecodes for Chapter 1
│   ├── MRK_02_timing.txt
│   └── MRK_03_timing.txt
│
├── backgrounds/              # Visual background loops and static canvas images
│   ├── nature_loop_16x9.mp4  # Widescreen video loop for landscape videos
│   ├── vertical_sky_9x16.mp4 # Vertical loop for YouTube Shorts / TikTok Reels
│   └── abstract_bg.png       # Static high-resolution background image
│
└── assets/                   # Branding, Bumpers & Thumbnails (Upcoming Features)
    ├── title_card.jpg        # Still image displayed at start (also serves as YouTube thumbnail!)
    ├── intro_bumper.mp3      # Short station/intro audio clip played before scripture starts
    └── outro_credits.mp3     # Short closing music played after scripture finishes
```

### Asset Type Guidelines:
1. **USFM Scripture (`usfm/`):** Place standard UTF-8 encoded `.SFM` or `.usfm` files here. VIDX automatically strips formatting noise (footnotes `\f`, cross-references `\x`, figures `\fig`) and targets the exact chapter requested by your timing file.
2. **Audio Recordings (`audio/`):** Use standardized audio exported from your AUDX pipeline. Supported formats include `.mp3`, `.wav`, `.aac`, and `.mpeg`. Ensure filenames clearly identify the book and chapter.
3. **Timing Maps (`timing/`):** Standard tab-delimited files (`start_sec \t end_sec \t segment_id`). Punctuation splits and verse fragments (`1a`, `1b`) are matched automatically.
4. **Backgrounds (`backgrounds/`):** You can use short looping video clips (`.mp4`, `.mov`) or static images (`.jpg`, `.png`). If your video loop is shorter than the chapter audio, VIDX will automatically loop it (`loop_background: true`) to match the exact duration!
5. **Title Cards & Bumpers (`assets/` - Upcoming v0.3 Features):** You can prepare still title images (`title_card.jpg`) to serve as video intros and YouTube thumbnails, along with introductory/closing audio bumpers (`intro.mp3` / `outro.mp3`). VIDX will automatically offset subtitle timestamps to account for intro audio delays!

---

## ⚙️ Step 2: Creating Your Configuration (`project.yaml`)

You can copy an existing template from our `examples/` folder or create a custom `project.yaml` file in your workspace directory:

```yaml
project:
  name: "Sindhi Mark Release"
  output_dir: "release_videos"
  generate_only: false          # Set true if you only want SRT/ASS subtitle files

video:
  resolution: "1920x1080"       # Use "1080x1920" for vertical reels/shorts
  fps: 24
  codec: "libx264"
  preset: "fast"
  crf: 22                       # 22 gives sharp text and crisp backgrounds
  background_media: "backgrounds/nature_loop.mp4"
  loop_background: true
  scaling_mode: "pad"

style:
  verse:
    font: "Bailey"              # Ensure font is installed on Windows/macOS/Linux
    size: 50
    color: "#FFFFFF"
    outline_color: "#000000"
    outline_width: 3
    shadow: 1
    alignment: 2                # Bottom-Center
    margin_bottom: 60
    margin_lr: 60
    background_box: true
    background_color: "#000000" # Base color for background box
    background_opacity: 0.65    # Configurable opacity (0.65 = 65% opaque / 35% transparent)

  heading:
    font: "Bailey"
    size: 60
    color: "#FFD400"            # Gold heading text
    alignment: 8                # Top-Center
    margin_vertical: 80
    bold: true

  verse_number:
    show: true
    color: "#FFC080"
    size: 38
    on_every_segment: false     # Reference prefix only shown on first fragment (2a)

jobs:
  - usfm: "usfm/42MRKsnd.SFM"
    timing: "timing/MRK_01_timing.txt"
    audio: "audio/SND-MRK-1.mp3"
    output: "release_videos/Mark_Chapter_01.mp4"
    
  - usfm: "usfm/42MRKsnd.SFM"
    timing: "timing/MRK_02_timing.txt"
    audio: "audio/SND-MRK-2.mp3"
    output: "release_videos/Mark_Chapter_02.mp4"
```

---

## 🎬 Step 3: Performing a 10-Second Shakedown Test

Before committing to a full render (which can take several minutes per chapter), always run a **10-second shakedown test** to verify that your fonts look great and your background video scales correctly:

```bash
# Test rendering using one of our built-in examples or your custom yaml
vidx -c examples/sindhi_mark_16x9.yaml -t 10
```

Open `output/Mark_Chapter_05_16x9.mp4` in your media player (VLC, Windows Media Player) and verify:
1. Are section titles (`\s1`) showing at the top center in gold?
2. Are verse references (`Mark 5:1`) prefixing the dialogue lines clearly?
3. Are Indic/Devanagari/Sindhi/Malayalam conjuncts and nuktas shaping properly without any square "tofu" blocks?
4. Is the semi-transparent background box providing clean readability over the video background?

---

## 🚀 Step 4: Whole-Book Batch Rendering & Multimedia Enhancements

When you are ready to produce an entire Scripture book (e.g., Gospel of Mark, Chapters 1 through 16), list all chapter jobs under the `jobs` block in your configuration file. Because VIDX's internal USFM parser automatically matches chapters, you only need **one shared `.SFM` book file** for the entire job queue! (See [examples/whole_book_batch.yaml](../examples/whole_book_batch.yaml) for a complete working template).

### 1. Parallel Multi-Worker Rendering & GPU Acceleration (`-w`, `--gpu`)
Rendering dozens of chapters sequentially can take hours. To accelerate production, use the `-w` (workers) flag to spawn multiple concurrent CPU rendering processes, and pass `--gpu` (or set `video.gpu: true` in your YAML) to enable NVIDIA NVENC or Intel QSV hardware encoding:

```bash
# Render 4 chapters simultaneously with hardware GPU acceleration!
vidx -c examples/whole_book_batch.yaml -w 4 --gpu

# Add -y if your background video/image is above your target resolution (e.g. a
# 4K clip on a 1080p project) - it auto-confirms the one-time downscale-to-1080p
# prompt instead of pausing the batch to wait for input:
vidx -c examples/whole_book_batch.yaml -w 4 --gpu -y
```

> **Real-world worker tuning note:** a controlled comparison on a 21-chapter book showed `-w 4`
> finishing in roughly 1.6x less wall-clock time than `-w 1` — but each chapter took ~2.5x longer
> to encode individually (NVENC encoder contention when 4 processes share one GPU). `-w 4` is
> usually still the better choice for fastest turnaround, but if the machine is shared with other
> work, `-w 2` may be a better balance. See `docs/todo.md` for the full numbers.

During a multi-worker batch run, VIDX displays an interactive, real-time terminal UI showing:
*   **Worker Mapping:** A dedicated live progress bar for each active worker (`[Worker 1] Mark Ch 05: 45% ━━━╸━━━━━━`).
*   **Live Metrics:** Real-time encoding speed (`2.3x`), frames per second (`fps`), elapsed time, ETA, and **GPU usage/time tracking**.
*   **Global Batch Summary:** A master progress bar tracking completed chapters versus total remaining jobs in the queue.

> [!TIP]
> **Automatic 1080p Preprocessing & Loop Caching:** If your background media is high-resolution 4K (> 1080p), VIDX automatically downscales and caches a 1080p version (`*_1080p.mp4`) in the background before batch rendering begins. If `loop_crossfade_sec` is enabled, VIDX pre-calculates and bakes seamless crossfades into the cached loop (`*_xf1.0s.mp4`), completely eliminating CPU decoding bottlenecks and preventing jump cuts when loops repeat!

### 2. Adding Title Cards & Thumbnails
You can attach a still title image that displays for a set number of seconds before scripture reading begins:
```yaml
video:
  title_card: "assets/title.jpg" # Doubles as your YouTube/social media video thumbnail!
  title_duration: 4.0            # Duration in seconds
```

### 3. Audio Bumpers & Looped Background Music (BGM)
Give your videos a broadcast-ready feel by adding introductory/concluding audio clips and seamless background instrumental music:
```yaml
audio:
  intro_clip: "assets/intro.mp3"       # Plays before scripture starts (subtitles shift automatically!)
  outro_clip: "assets/outro.mp3"       # Plays after scripture concludes
  background_music: "assets/bgm.mp3"   # Automatically looped to match reading duration
  background_music_volume: 0.15        # Blended cleanly without reducing narrator voice volume
```

### 4. Custom Watermarks & Channel Corner Logos
Add your station or ministry logo to any corner of the screen with alpha transparency:
```yaml
video:
  watermark:
    image: "assets/logo.png"
    position: "top-right"    # top-left, top-right, bottom-left, bottom-right, or custom coordinates
    margin: 30               # Distance from screen edge in pixels
    scale: 0.15              # Width relative to video width (15%)
    opacity: 0.85            # Alpha transparency
```

### 5. Smooth Audio Fade-In & Fade-Out Transitions
Apply clean audio transitions at the start and end of chapter videos:
```yaml
audio:
  fade_in_sec: 1.5           # Smooth fade-in over first 1.5 seconds
  fade_out_sec: 2.0          # Smooth fade-out over last 2.0 seconds
```

---

## 🚀 YouTube Publishing & Team Distribution Guide

VIDX features a built-in **2-Stage Hybrid Publishing Architecture** designed to overcome Google API quota restrictions and simplify video distribution for translation teams operating in remote or low-bandwidth environments.

### 1. Understanding Google API Quotas & The Outbox Manifest
Google Cloud Platform enforces a daily quota of **10,000 units per project** on the YouTube Data API v3. 
* Uploading a single video costs **~1,600 units**, attaching a thumbnail costs **50 units**, and adding to a playlist costs **50 units** (~1,700 units total per chapter).
* This allows an automated tool to publish **5 to 6 chapter videos per day** per Google project before hitting the limit.

To prevent long multi-hour batch runs from failing when this daily quota is reached, VIDX decouples video rendering from online distribution using an **Outbox Manifest**:
1. When you run `vidx -c project.yaml`, VIDX renders all video files and creates a database called `publish_manifest.json` inside your output folder.
2. When you are ready to upload online, you run:
   ```bash
   vidx --manifest output/publish_manifest.json
   ```
3. VIDX uploads videos sequentially. When the 10,000-unit daily limit is reached, **VIDX cleanly pauses**, preserves all progress in `publish_manifest.json`, and advises you to run the exact same command tomorrow after Google resets your quota! Failed or interrupted uploads will automatically retry without re-rendering any video files.

---

### 2. How to Share VIDX with Others (Team Configuration)
When distributing VIDX to field technicians, translators, or media coordinators, you have two flexible workflows depending on their internet access and technical setup:

#### Option A: Offline "YouTube Studio Ready" Packages (Zero Setup Required)
For remote team members without stable internet or Google API developer credentials, VIDX generates an offline upload kit automatically.
In your project YAML configuration, ensure this option is enabled:
```yaml
publishing:
  platform: "youtube"
  enabled: false                    # Set false so rendering runs without API login
  generate_offline_package: true    # Generates studio copy-paste folders
  privacy_status: "unlisted"
  playlist_name: "Gospel of Matthew — Sindhi Audio Bible"
  title_template: "{book} Chapter {chapter:02d} — {language} Audio Bible"
  description_template: |
    Listen to {book} Chapter {chapter} in {language}.
    Generated automatically by VIDX Scripture Video Engine.
  tags: ["AudioBible", "{language}", "{book}", "Scripture"]
```
When team members run the batch render, VIDX creates an isolated folder inside `output/YouTube_Upload_Package/` for each chapter containing:
* The rendered `.mp4` video.
* The `.jpg` title card thumbnail.
* A formatted `metadata.txt` file containing the exact title, description, and hashtags.
**How they use it:** Team members simply open [YouTube Studio](https://studio.youtube.com/) in their web browser, drag-and-drop the MP4 and thumbnail, and copy-paste the text from `metadata.txt`! No Google Cloud Console or API setup is required.

#### Option B: Automated API Publishing with Team Members
If your team members want to run automated batch uploading directly from their terminal using `vidx --manifest`, follow these modern OAuth 2.0 setup steps:

##### Step 1: Set up Google Cloud Credentials
1. Go to the **[Google Cloud Console](https://console.cloud.google.com/)** and create/select a project.
2. Navigate to **APIs & Services > Library**, search for **"YouTube Data API v3"**, and click **Enable**.
3. Navigate to **APIs & Services > OAuth consent screen** (or **Google Auth Platform / Audience** in newer UI layouts):
   - Choose **External** (or Internal if within a Google Workspace organization) and click **Create**.
   - Fill in your App name (e.g., `VIDX Scripture Uploader`) and user support email.
   - Under **Test users**, **you MUST click "+ ADD USERS" and add the Google/YouTube email addresses of every team member who will be uploading videos.** (Apps in testing status will reject logins from users not explicitly listed here).
4. Navigate to **APIs & Services > Credentials**:
   - Click **+ CREATE CREDENTIALS** -> **OAuth client ID**.
   - Select **Desktop app** as the Application type and click **Create**.
   - Click **DOWNLOAD JSON** to download the OAuth client secret file.

##### Step 2: Configure Team Computers
1. Share the downloaded JSON credentials file with your authorized team members (or have them create their own free Google Cloud projects if they need their own separate 10,000 daily quota allowance).
2. On the team member's Windows computer, open PowerShell and create the configuration directory:
   ```powershell
   New-Item -ItemType Directory -Force "$HOME\.vidx"
   ```
3. Copy the shared credentials file into that directory and rename it to `client_secrets.json`:
   ```powershell
   Copy-Item "path\to\downloaded_secret.json" "$HOME\.vidx\client_secrets.json"
   ```
4. Run the upload manifest from terminal:
   ```powershell
   vidx --manifest output\publish_manifest.json
   ```
5. A browser tab will open on the team member's computer. They must log in with their authorized Google account. If a screen says *"Google hasn't verified this app"*, instruct them to click **Advanced** -> **Go to VIDX Scripture Uploader (unsafe)** -> **Continue/Allow**.
6. VIDX saves a secure OAuth refresh token locally in `~/.vidx/youtube_token.json` and automatically begins chunked, resumable background uploads!

---

## ❓ Troubleshooting & FAQ

### Q1: My text appears as square "tofu" boxes or question marks.
**Cause:** The font specified in `style.verse.font` or `style.heading.font` is not installed on your operating system, or FFmpeg cannot locate it.
**Solution:**
- Check installed Windows fonts or run `fc-list` on Linux.
- Set `font: "Nirmala UI"`, `"Bailey"`, or `"Mangal"` on standard machines.
- Ensure your FFmpeg build includes `--enable-fontconfig` and `--enable-libass`.

### Q2: How do I create vertical videos for YouTube Shorts or Instagram Reels?
**Solution:** Change the resolution and safety margins in your YAML config (or use our `examples/malayalam_philemon_9x16.yaml` template):
```yaml
video:
  resolution: "1080x1920"
  scaling_mode: "crop"          # Automatically crops landscape backgrounds to fill vertical screens
style:
  verse:
    margin_bottom: 140          # Elevated bottom margin avoids TikTok/Reels UI overlay buttons!
    margin_lr: 45
```

### Q3: Can I generate subtitle files (.srt or .ass) without creating video?
**Solution:** Yes! VIDX has a built-in **dual-purpose subtitle extraction mode**. You can output standard SubRip (`.srt`) or Aegisub (`.ass`) subtitle files instantly without running FFmpeg video rendering:

```bash
# Extract both SRT and ASS subtitles for an entire batch YAML project
vidx -c examples/sindhi_mark_16x9.yaml --generate-only --format both

# Or generate a standalone SRT subtitle file directly from command line
vidx --generate-only --format srt --usfm usfm/42MRKsnd.SFM --timing timing/MRK_01_timing.txt -o Mark_01.srt
```
In subtitle-only mode, audio soundtrack files are not required—you can extract broadcast subtitles from text and timing files alone!
