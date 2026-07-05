# USFM2VDO — Project Brief (Revised)

> **Revision note:** Updated after discovering the existing [usfm-converter](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter) project. This changes the picture significantly.

---

## 1. What Already Exists

The biggest thing my earlier analysis got wrong: **the hardest part of this project is already built.**

The [usfm_to_srt.py](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter/usfm_to_srt.py) converter (v0.1.1-alpha, 778 lines) already handles:

| Capability | Status | Implementation |
|---|---|---|
| USFM parsing with chapter targeting | ✅ Done | [USFMParser](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter/usfm_to_srt.py#L23-L140) class |
| Footnote/cross-ref stripping (`\f`, `\x`) | ✅ Done | [_clean_text()](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter/usfm_to_srt.py#L34-L55) |
| Timing file parsing (verse + phrase level) | ✅ Done | [TimingParser](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter/usfm_to_srt.py#L143-L199) class |
| Phrase-level text segmentation (2a, 2b, 7f) | ✅ Done | [TextSegmenter](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter/usfm_to_srt.py#L202-L253) class |
| Section heading extraction (`\s`, `\s1`) | ✅ Done | Lines 96–103 |
| SRT generation with timestamps | ✅ Done | [SRTGenerator](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter/usfm_to_srt.py#L256-L385) class |
| Batch processing (full book) | ✅ Done | [convert_batch()](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter/usfm_to_srt.py#L490-L600) |
| Combined output (all chapters → one file) | ✅ Done | `--combined` flag |
| Input validation | ✅ Done | [validator.py](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter/validator.py) (694 lines) |
| Standalone EXE build | ✅ Done | [build.bat](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter/build.bat) + PyInstaller |

> [!IMPORTANT]
> This means the **"core engineering challenge"** I flagged in the previous brief — USFM+timing→subtitle alignment — is already solved and tested with real Sindhi/Devanagari data. The usfm2vdo project doesn't need to rewrite this. It needs to **extend** it.

---

## 2. What This Project Is

**usfm2vdo** is the layer that sits *on top of* the existing usfm-converter and adds:

1. **`.ass` subtitle output** instead of (or in addition to) `.srt`
2. **FFmpeg command generation** to composite background + audio + subtitles → video
3. **Batch video rendering** across chapters/books
4. **Configuration** for visual styling (fonts, colours, layout, aspect ratio, logos)

That's it. The USFM parsing, timing alignment, and text segmentation are inherited.

```
┌──────────────────────────────────────────────────────────┐
│                     usfm2vdo                             │
│                                                          │
│  ┌─────────────┐  ┌───────────────┐  ┌───────────────┐  │
│  │ ASS         │  │ FFmpeg Cmd    │  │ Batch Video   │  │
│  │ Generator   │  │ Builder       │  │ Runner        │  │
│  │ (new)       │  │ (new)         │  │ (new)         │  │
│  └──────┬──────┘  └───────┬───────┘  └───────┬───────┘  │
│         │                 │                   │          │
├─────────┴─────────────────┴───────────────────┴──────────┤
│                                                          │
│              usfm-converter (existing)                   │
│  USFMParser · TimingParser · TextSegmenter · Validator   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 3. What This Project Is NOT

| Not This | Why |
|---|---|
| A video editor | No preview, no timeline, no manual arrangement. Configure → render. |
| A USFM parser | Already built. We consume it. |
| A content creation tool | All content already exists. Pure repurposing. |
| A hosting/streaming platform | No YouTube accounts, no channel management. |
| A replacement for professional video production | "Good enough for YouTube/social" — not broadcast cinema. |
| A mobile app | Desktop CLI tool for translation coordinators. |

---

## 4. Why `.ass` Over `.srt`

You mentioned interest in `.ass` format. Here's the concrete comparison with what it enables:

### What `.srt` can do (current state)
```srt
1
00:00:05,060 --> 00:00:08,880
येशुअ ऐं संदस जा चेला गलील झील जे उन पार गिरासेनियों जे इलाकन में पौंता।
```
- Plain white text, no styling control
- Position is always bottom-center (player decides)
- No background box, no outline control
- No way to differentiate section headings from verse text
- No verse number styling

### What `.ass` enables
```ass
[Script Info]
Title: Mark Chapter 5 - Sindhi
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Verse,Noto Sans Devanagari,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,2,40,40,60,1
Style: Heading,Noto Sans Devanagari,56,&H0000D4FF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,5,40,40,80,1
Style: VerseNum,Noto Sans Devanagari,36,&H0080C0FF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,7,40,40,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:02.88,0:00:05.06,Heading,,0,0,0,,दुष्‍टआत्माउन जे वशअ मां छुटकारो
Dialogue: 0,0:00:05.06,0:00:08.88,Verse,,0,0,0,,{\an8}मरकुस 5:1\Nयेशुअ ऐं संदस जा चेला गलील झील जे उन पार गिरासेनियों जे इलाकन में पौंता।
```

| Feature | `.srt` | `.ass` |
|---|---|---|
| Custom font & size | ❌ | ✅ Per-style definition |
| Text outline & shadow | ❌ | ✅ Configurable thickness, colour |
| Semi-transparent background box | ❌ | ✅ `BackColour` with alpha |
| Position control (top/center/bottom) | ❌ | ✅ `Alignment` field (numpad layout) |
| Different styles for headings vs verses | ❌ | ✅ Named styles per dialogue line |
| Verse number in a different colour/size | ❌ | ✅ Inline override tags `{\c&H...&}` |
| Margins per aspect ratio | ❌ | ✅ `MarginL`, `MarginR`, `MarginV` |
| Word wrap control | ❌ | ✅ `WrapStyle` + `\q` tags |
| Line breaks at exact positions | ❌ | ✅ `\N` for hard line breaks |
| Fade in/out | ❌ | ✅ `{\fad(300,200)}` |

> [!TIP]
> The key architectural decision: The existing `SRTGenerator` class can be **paralleled** by an `ASSGenerator` class that consumes the same `USFMParser` and `TimingParser` objects but outputs `.ass` format instead. No need to rewrite the parsing logic.

---

## 5. Revised Risk Assessment

With the existing converter as a foundation, the risk picture changes dramatically:

| Risk | Previous | Now | Reason |
|---|---|---|---|
| USFM ↔ timing alignment | 🔴 HIGH | 🟢 LOW | Already solved in [TextSegmenter](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm-converter/usfm_to_srt.py#L202-L253) |
| USFM markup stripping | 🟡 MEDIUM | 🟢 LOW | Already handled (though `\fig` stripping [needs fixing](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm2vdo/src/MRK_05_Segmented.srt#L259)) |
| `.ass` styling/positioning | N/A | 🟡 MEDIUM | New — needs correct alignment math for 3 aspect ratios |
| Complex script rendering (HarfBuzz) | 🟡 MEDIUM | 🟡 MEDIUM | Unchanged — depends on FFmpeg build |
| FFmpeg command correctness | N/A | 🟡 MEDIUM | New — filter graph syntax is finicky |
| Long verse overflow | 🟡 LOW-MED | 🟢 LOW | `.ass` `WrapStyle` handles this better than `.srt` |
| Batch rendering time | N/A | 🟡 MEDIUM | Full NT = hours. Need progress reporting + parallelism option |

### Remaining Known Bug
The existing converter doesn't strip `\fig ... \fig*` markers. Evidence: [MRK_05_Segmented.srt line 259](file:///C:/Users/BCS_Support/Documents/dev/nlci/usfm2vdo/src/MRK_05_Segmented.srt#L259) contains `|src="lb00310.jpg" size="col" ref="5:29"` as visible subtitle text. This needs to be fixed in the converter's `_clean_text()` method before we build on top of it.

---

## 6. Architecture

### Module Breakdown

**Module 1: `ASSGenerator`** (new, ~200–300 lines)
- Consumes the same `USFMParser` + `TimingParser` objects as `SRTGenerator`
- Outputs `.ass` file with:
  - Script info section (resolution, wrap style)
  - Named styles: `Verse`, `Heading`, `VerseNum` (configurable)
  - Dialogue events with correct timestamps and style references
- Configurable: font, size, colours, outline, shadow, margins, alignment position

**Module 2: `FFmpegBuilder`** (new, ~150–200 lines)
- Takes: config + `.ass` path + audio path + background path
- Builds the FFmpeg command string with correct filter graph
- Handles:
  - Background looping (`-stream_loop -1`) for videos, scaling for images
  - Audio input as master clock
  - ASS subtitle burn-in via `ass` filter (not `subtitles` — `ass` is more reliable for pre-styled files)
  - Logo overlay via `overlay` filter (optional)
  - Aspect ratio scaling/cropping for 16:9, 9:16, 1:1
  - Duration trimming (`-shortest`)
  - Codec selection (default `libx264`, optional hardware accel)

**Module 3: `BatchRunner`** (new, ~100–150 lines)
- Iterates chapters from config
- For each chapter: calls ASSGenerator → calls FFmpegBuilder → runs FFmpeg
- Progress reporting (chapter X of Y, estimated time remaining)
- Error recovery (skip failed chapters, continue)
- Optional parallel execution (configurable worker count)

**Module 4: `Config`** (new, ~50–80 lines)
- YAML config loader with defaults
- Path validation
- FFmpeg availability check

### What we reuse from usfm-converter (no changes needed)
- `USFMParser` — as-is
- `TimingParser` — as-is
- `TextSegmenter` — as-is
- `BatchValidator` — as-is (optional validation before rendering)

### What we fix in usfm-converter
- `_clean_text()` — add `\fig ... \fig*` stripping

---

## 7. Configuration Design

```yaml
# usfm2vdo project config
project:
  name: "Sindhi NT - Mark"
  language: "snd"

# === INPUTS (paths relative to config file) ===
input:
  usfm: "./42MRKsnd.SFM"
  audio_dir: "./audio/mark/"
  timing_dir: "./mrk-timings/"
  # Filename patterns (use {chapter} placeholder)
  audio_pattern: "C01-01-MRK-{chapter:02d}*.mp3"
  timing_pattern: "C01-01-MRK-{chapter:02d}-timing.txt"

# === OUTPUT ===
output:
  dir: "./output/videos/"
  format: "mp4"

# === VIDEO SETTINGS ===
video:
  aspect_ratio: "16:9"       # "16:9" | "9:16" | "1:1"
  resolution: "1920x1080"    # auto-calculated from aspect if omitted
  fps: 30
  codec: "libx264"           # or "h264_nvenc" for GPU
  crf: 23                    # quality (lower = better, 18-28 range)
  background: "./assets/bg1.mp4"   # video or image
  logo: "./assets/logo.png"        # optional
  logo_position: "top-right"       # top-left | top-right | bottom-left | bottom-right
  logo_scale: 0.08                 # % of video width
  logo_opacity: 0.7

# === TEXT STYLING (maps to .ass styles) ===
style:
  verse:
    font: "Noto Sans Devanagari"
    size: 48
    color: "#FFFFFF"
    outline_color: "#000000"
    outline_width: 3
    shadow: 1
    background_box: true
    background_color: "#00000080"   # semi-transparent black
    position: "bottom"              # "top" | "center" | "bottom"
    margin_bottom: 60
  heading:
    font: "Noto Sans Devanagari"
    size: 56
    color: "#FFD400"                # gold
    bold: true
    position: "center"
  verse_number:
    show: true
    color: "#FFC080"
    size: 36

# === BATCH SETTINGS ===
batch:
  chapters: "all"             # or "1-5" or "3,7,12"
  parallel_workers: 2         # number of simultaneous FFmpeg processes
  skip_existing: true         # don't re-render if output exists
```

---

## 8. UI/UX: CLI First

**v1 = CLI + YAML config** (recommended, as before)

```bash
# Render all chapters defined in config
usfm2vdo render --config project.yaml

# Render specific chapter for testing
usfm2vdo render --config project.yaml --chapter 5

# Generate .ass files only (no video rendering)
usfm2vdo subtitle --config project.yaml

# Validate inputs before rendering
usfm2vdo validate --config project.yaml

# Preview: render first 15 seconds of one chapter
usfm2vdo preview --config project.yaml --chapter 5
```

This is the right choice because:
- The target users have IT coordinators who are comfortable with config files
- A config file is reproducible, shareable, and version-controllable
- A GUI can be layered on top later — it would just generate this same YAML and call the same CLI

---

## 9. Revised Roadmap & Advisory Council Conditions

Based on the Advisory Council review, the build is approved under three non-negotiable conditions:
1. **Import over fork:** Import `usfm-converter` as a Python package rather than duplicating code, ensuring bug fixes (like `\fig` stripping) benefit both tools.
2. **Phase 0 Spike:** Gate the entire roadmap on a half-day technical spike to prove FFmpeg + `libass` correctly renders complex Indic/Devanagari scripts and diacritics on the field coordinator's hardware.
3. **Re-priced timeline:** Budget **7–10 working days** total to account for FFmpeg filtergraph complexities and edge cases.

### Phase 0: The Complex Script Rendering Spike (Half-Day — GATEKEEPER)
- Create a minimal `.ass` file with actual Sindhi Devanagari scripture (Mark ch5) and Google Noto Sans Devanagari font.
- Run a direct `ffmpeg` command using the `ass` filter over sample audio and background video.
- Verify exact rendering of conjunct ligatures, nuktas, and diacritics (e.g., `ब॒`, `ड॒`, `ड़`, `थ्यूं`) without character dropout ("tofu").
- **Success metric:** A 15-second test video confirmed clean by field coordinators. *If this fails, investigate font shaping / libass builds before proceeding.*

### Phase 1: `.ass` Generator & Pipeline Integration (2–3 days)
- Import `usfm-converter` as a package and apply the `\fig` marker stripping fix upstream.
- Create `ASSGenerator` class consuming `USFMParser` and `TimingParser` to output `.ass` files with styled headings, verse numbers, and dialogue lines.
- Build the core FFmpeg command builder for a single chapter.
- **Success metric:** Full Mark Chapter 5 video automatically rendered from raw input files.

### Phase 2: Configuration, Layouts & Batch Engine (3–4 days)
- Implement YAML config loader (`project.yaml`).
- Add responsive layout math in `.ass` and FFmpeg filtergraphs for 16:9 (Landscape), 9:16 (Portrait Shorts/Reels), and 1:1 (Square).
- Add support for static images vs. looping background video (`-stream_loop -1`) and logo watermarking (`overlay` filter).
- Build the batch runner to process entire books with progress reporting and error recovery.
- **Success metric:** Mark Gospel (all 16 chapters) automatically rendered into 16:9 and 9:16 formats.

### Phase 3: Polish, Performance & Field Distribution (2–3 days)
- Add EBU R128 audio loudness normalization (`loudnorm`).
- Add multi-process parallel rendering to maximize CPU utilization.
- Add `preview` CLI command (renders first 15 seconds of a chapter for quick verification).
- Write comprehensive installation and field deployment documentation.
- **Success metric:** Translation IT coordinators can install, configure, and run unattended batch renders.

---

## 10. Efficiency & Performance

| Operation | Time | Notes |
|---|---|---|
| USFM → ASS subtitle generation | < 1 sec/chapter | Pure text processing, negligible |
| FFmpeg render (1080p, 5-min chapter, static background) | ~30–60 sec | CPU-bound, `libx264` |
| FFmpeg render (1080p, 5-min chapter, video background) | ~45–90 sec | Adds video decode overhead |
| FFmpeg render with GPU (`h264_nvenc`) | ~5–15 sec | 5–10x faster if GPU available |
| Full Mark (16 chapters, ~1hr audio) | ~15–25 min CPU | Parallelism cuts this in half |
| Full NT (~260 chapters, ~20hr audio) | ~3–6 hrs CPU | Overnight batch job |
| Output file size (1080p, static bg) | ~10–15 MB/min | Full Mark ≈ 600 MB |
| Output file size (720p, static bg) | ~5–8 MB/min | Half the storage |

---

## 11. Potential Pitfalls

### Data Risks
- **Post-timing USFM edits:** If USFM text is edited after timing was created, phrase segment counts won't match. The existing converter already warns about this (`[!] 0 subtitles`), but we should surface this more clearly.
- **Missing audio files:** Timing exists but audio doesn't. Must validate upfront.
- **`\fig` bug:** Must be fixed upstream in `usfm-converter` before generating `.ass` files. Already found in sample data.

### Technical Risks
- **FFmpeg not installed or wrong build:** Must check for `libass` and HarfBuzz support. On Windows, the popular gyan.dev builds include it. (Tested in Phase 0).
- **Font not found:** FFmpeg silently falls back to a default font that may not support the script. Must verify and fail loudly.
- **File encoding:** USFM files may be UTF-8, UTF-8 with BOM, or UTF-16. Current converter assumes UTF-8 only.

### Scope Risks
- **Feature creep into video editing territory.** Resist the urge to add transitions, text animations, or per-verse background images. Those belong in a different tool.
- **`.ass` complexity spiral.** The format supports extreme styling (karaoke, transforms, clip masks). We should use a small, well-defined subset and not chase every possible feature.

---

## 12. Open Questions Needing Decisions

1. **Section headings (`\s`):** Display as a styled subtitle (like current SRT), display as a title card (separate visual treatment), or make it configurable?

2. **Verse numbers on screen:** Show them? If yes: inline with text (`5:7 येशुअ...`) or as a separate small label in a corner?

3. **Phrase vs. verse display:** When timing is phrase-level, should subtitles show one phrase at a time (current behaviour) or group into full verses? Or make this configurable?

4. **Background for v1:** Support still images only (simpler FFmpeg command), video loops only, or both?

5. **Relationship to usfm-converter:** *[RESOLVED by Council & v0.2 Evolution: Originally imported as an external Git library, `usfm-converter` has now been fully internalized directly into `vidx` as `vidx.usfm_parser` (`usfm_parser.py`). This eliminates external network Git dependency issues during standalone PyInstaller (.exe) builds and enables VIDX to serve as a high-speed dual-purpose subtitle generator (`--generate-only --format srt|ass|both`).]*

6. **Project language confirmed as Python?** The converter is Python. Building on top in Python is the natural choice. Just confirming.
