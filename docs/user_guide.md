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
[USFM Scripture]   ──► [ Aeneas ] ──► Timing Map (.txt)       ┼─► [ VIDX ] ──► MP4 Video
                                                             │
[Background Media] ──► (Video Loop / Image) ─────────────────┘
```

---

## 🛠️ Step 1: Preparing Your Assets

For each book or chapter you wish to convert, gather your files into a clean workspace structure. For example:

```
my_project/
├── audio/
│   ├── SND-MRK-1.mp3
│   └── SND-MRK-2.mp3
├── timing/
│   ├── MRK_01_timing.txt
│   └── MRK_02_timing.txt
├── usfm/
│   └── 42MRKsnd.SFM
└── backgrounds/
    └── nature_loop.mp4
```

### Tips for Timing Files:
- Ensure your timing files use tab-delimited or standard Aeneas format (`start_sec   end_sec   segment_id`).
- Verse fragments (`2a`, `2b`) will automatically be matched and split across dialogue screens by `vidx`.

---

## ⚙️ Step 2: Creating Your Configuration (`config.yaml`)

Create a `project.yaml` file in your workspace directory:

```yaml
project:
  name: "Sindhi Mark Release"
  output_dir: "release_videos"

video:
  resolution: "1920x1080"       # Use "1080x1920" for vertical reels/shorts
  fps: 24
  codec: "libx264"
  preset: "fast"
  crf: 22                       # 22 gives sharp text and crisp backgrounds
  background_media: "backgrounds/nature_loop.mp4"
  loop_background: true

style:
  verse:
    font: "Nirmala UI"          # Ensure font is installed on Windows/macOS/Linux
    size: 50
    color: "#FFFFFF"
    outline_color: "#000000"
    outline_width: 3
    shadow: 1
    alignment: 2                # Bottom-Center
    margin_bottom: 70
    background_box: true
    background_color: "#000000A0" # Slightly darker background box for readability

  heading:
    font: "Nirmala UI"
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
vidx -c project.yaml -t 10
```

Open `release_videos/Mark_Chapter_01.mp4` in your media player (VLC, Windows Media Player) and verify:
1. Are section titles (`\s1`) showing at the top center in gold?
2. Are verse references (`Mark 1:1`) prefixing the dialogue lines clearly?
3. Are Indic/Devanagari conjuncts and nuktas (`ड॒`, `बे॒`) shaping properly without any square "tofu" blocks?

---

## 🚀 Step 4: Full Batch Rendering

Once you are satisfied with the 10-second test preview, run the full batch job:

```bash
# Sequential rendering
vidx -c project.yaml

# Multi-core concurrent rendering (e.g., render 4 chapters simultaneously)
vidx -c project.yaml -w 4
```

---

## ❓ Troubleshooting & FAQ

### Q1: My text appears as square "tofu" boxes or question marks.
**Cause:** The font specified in `style.verse.font` or `style.heading.font` is not installed on your operating system, or FFmpeg cannot locate it.
**Solution:**
- Check installed Windows fonts or run `fc-list` on Linux.
- Set `font: "Nirmala UI"` or `"Mangal"` on standard Windows machines.
- Ensure your FFmpeg build includes `--enable-fontconfig` and `--enable-libass`.

### Q2: How do I create vertical videos for YouTube Shorts or Instagram Reels?
**Solution:** Change the resolution in your YAML config:
```yaml
video:
  resolution: "1080x1920"
  scaling_mode: "crop"          # Automatically crops landscape backgrounds to fill vertical screens
```

### Q3: Can I generate subtitle files without creating video?
**Solution:** Yes! Use the `--generate-only` flag to output Aegisub-compatible `.ass` files:
```bash
vidx --generate-only --usfm usfm/42MRKsnd.SFM --timing timing/MRK_01_timing.txt -o Mark_01.ass
```
