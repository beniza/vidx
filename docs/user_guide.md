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

## 🛠️ Step 1: Preparing Your Assets

For each book or chapter you wish to convert, gather your files into a clean workspace structure. Notice that because VIDX includes an intelligent internal USFM parser, **multiple chapters can share a single book-level USFM file**:

```
my_project/
├── audio/
│   ├── SND-MRK-1.mp3
│   └── SND-MRK-2.mp3
├── timing/
│   ├── MRK_01_timing.txt
│   └── MRK_02_timing.txt
├── usfm/
│   └── 42MRKsnd.SFM          # Single book file shared across all chapters!
└── backgrounds/
    └── nature_loop.mp4
```

### Tips for Timing Files:
- Ensure your timing files use tab-delimited or standard Aeneas format (`start_sec   end_sec   segment_id`).
- Verse fragments (`2a`, `2b`) will automatically be matched and split across dialogue screens by `vidx`.

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

## 🚀 Step 4: Full Batch Rendering

Once you are satisfied with the 10-second test preview, run the full batch job:

```bash
# Sequential rendering
vidx -c examples/sindhi_mark_16x9.yaml

# Multi-core concurrent rendering (e.g., render 4 chapters simultaneously)
vidx -c examples/malayalam_philemon_16x9.yaml -w 4
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
