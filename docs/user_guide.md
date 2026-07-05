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
```

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
