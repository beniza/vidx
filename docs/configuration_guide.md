# VIDX Configuration & Bulk Processing Guide
> Exhaustive reference for configuring VIDX YAML files for single chapters, whole books, entire New Testaments, and dual-purpose subtitle generation.

---

## 📖 1. Overview & YAML Anatomy

VIDX uses human-readable YAML configuration files (`project.yaml`, `mal_16x9.yaml`, etc.) to orchestrate multi-media scripture video rendering and subtitle generation. A complete configuration file consists of these root blocks:

```yaml
project:
  # Global metadata, output directory, and execution mode
video:
  # Canvas dimensions, encoding codecs, framerate, and default background media
style:
  # Typography, colors, transparency, alignment, and margin safety zones
audio:
  # Encoding settings and background music
bumpers:
  # Optional intro/outro audio played around the narration
publishing:
  # YouTube upload settings and metadata templates
jobs:
  # List of chapters or books to process, with optional per-job overrides
```

---

## 🏗️ 2. The `project` Block

The `project` block controls project-wide metadata and general execution behaviors.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | String | `"VIDX Project"` | Descriptive title for logs and metadata. |
| `output_dir` | String | `"output"` | Root directory where generated MP4 videos and subtitle files will be written. |
| `generate_only` | Boolean | `false` | When set to `true`, **skips video rendering completely** and only generates `.ass` and/or `.srt` subtitle files. |
| `subtitle_format` | String | `"ass"` | Subtitle format to generate when `generate_only` is active or when keeping intermediate files. Options: `"ass"`, `"srt"`, or `"both"`. |

### Example
```yaml
project:
  name: "Malayalam Philemon Release"
  output_dir: "release/malayalam"
  generate_only: false
  subtitle_format: "both"
```

---

## 🎬 3. The `video` Block (Canvas & Media)

The `video` block defines the visual canvas, background media behaviors, and FFmpeg video encoding parameters.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `resolution` | String | `"1920x1080"` | Canvas width and height in pixels (e.g., `"1920x1080"`, `"1080x1920"`, `"3840x2160"`). |
| `fps` | Integer / Float | `24` | Frames per second for the output video (typically `24`, `25`, or `30`). |
| `codec` | String | `"libx264"` | FFmpeg video encoder codec. Recommended: `"libx264"` for maximum device compatibility. |
| `preset` | String | `"fast"` | Encoding speed vs. compression efficiency. Options: `ultrafast`, `superfast`, `veryfast`, `fast`, `medium`, `slow`. |
| `crf` | Integer | `23` | Constant Rate Factor (quality). Range: `0-51` (lower is higher quality). Recommended: `18-24`. |
| `background_media`| String | `""` | Default path to background loop (`.mp4`, `.mov`) or static image (`.jpg`, `.png`). |
| `loop_background` | Boolean | `true` | If `true`, loops video backgrounds that are shorter than the audio duration. |
| `scaling_mode` | String | `"pad"` | How background media scales to fit canvas: `"pad"` (letterbox/pillarbox), `"crop"` (fill screen without distortion), or `"stretch"`. |
| `codec` | String | `"libx264"` | Set to `"auto"` for GPU encoding: VIDX probes NVENC → QSV → AMF → VideoToolbox and falls back to `libx264`. **There is no `gpu:` key** — the CLI `--gpu` flag is the other way to request this. |
| `loop_crossfade_sec`| Float | `0.0` | Duration in seconds for dissolving loop seams during background preprocessing (e.g. `1.0`). Eliminates visual jumps when loops repeat! |
| `watermark` | Dictionary | `{}` | Optional corner logo branding overlay (see Watermark Configuration below). |

### Standard Aspect Ratio Guide
*   **16:9 Widescreen Landscape (YouTube, Broadcast, TV):** `resolution: "1920x1080"` or 4K `resolution: "3840x2160"`. Use `scaling_mode: "pad"` or `"crop"`.
*   **9:16 Portrait Vertical (YouTube Shorts, Instagram Reels, TikTok):** `resolution: "1080x1920"`. Always use `scaling_mode: "crop"` when using standard landscape background loops so they fill the vertical screen cleanly.
*   **1:1 Square (Instagram / Facebook Feed):** `resolution: "1080x1080"`.

### 🖼️ Custom Watermark & Channel Corner Logo Configuration
You can overlay a station logo or watermark PNG (with transparency) onto the video canvas using the `watermark` block inside `video`:
```yaml
video:
  watermark:
    image: "assets/logo.png"   # Path to watermark image (.png with transparency)
    position: "top-right"      # Options: top-left, top-right, bottom-left, bottom-right, or custom x:y
    margin: 30                 # Distance from video edge in pixels (default: 30)
    scale: 0.15                # Relative width percentage of video canvas (e.g. 0.15 = 15% width) or pixel width
    opacity: 0.8               # Transparency alpha from 0.0 (transparent) to 1.0 (opaque)
```

### ⚡ Automatic Background Preprocessing & Loop Caching
When processing bulk chapter queues, if your background video is high-resolution 4K (> 1080p), VIDX automatically downscales and caches a 1080p version (`*_1080p.mp4`) in the background before rendering begins. If `loop_crossfade_sec` is enabled, VIDX pre-calculates and bakes the crossfade transition into the cached loop (`*_xf1.0s.mp4`). This eliminates multi-worker CPU decoding bottlenecks and ensures zero visual jump cuts when looping indefinitely across chapters!

---

## 🎵 4. The `audio` Block (Bumpers & Background Music)

The `audio` block specifies encoding parameters as well as introductory/concluding audio bumpers and looped background music (BGM).

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `codec` | String | `"aac"` | FFmpeg audio encoder codec. |
| `bitrate` | String | `"192k"` | Audio encoding bitrate. |
| `sample_rate` | Integer | `48000` | Sample rate in Hz (`44100` or `48000`). |
| `background_music` | String | `""` | Optional path to background music (BGM) loop played continuously during scripture reading. |
| `background_music_volume` | Float | `0.15` | Volume level for background music (`0.0` to `1.0`). Recommended range: `0.10 - 0.20`. |
| `fade_in_sec` | Float | `0.0` | Duration in seconds for smooth audio fade-in at the start of the video (e.g., `1.5`). |
| `fade_out_sec`| Float | `0.0` | Duration in seconds for smooth audio fade-out at the end of the video (e.g., `2.0`). |

### Automatic Subtitle Timestamp Shifting & Audio Mixing
*   **Timestamp Shifting:** When `bumpers.intro_audio` is configured, VIDX automatically measures its exact duration and **offsets all subtitle timestamps in generated `.ass` and `.srt` files** by that duration. Scripture synchronization remains 100% frame-accurate!
*   **Looped BGM Blending:** When `background_music` is configured, VIDX automatically loops the background soundtrack to match the full duration of the scripture reading and blends it using FFmpeg's `amix` filter (`normalize=0`) so the narrator's voice volume is never attenuated.

---

## 🔔 4b. The `bumpers` Block (Intro & Outro Audio)

Intro and outro audio are configured in their **own top-level block**, not under `audio`.
Getting this wrong is silent: a misplaced key is simply ignored and no bumper is added.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `intro_audio` | String | *(unset)* | Audio played **before** the narration. VIDX measures its real duration and shifts every subtitle timestamp forward to match, so sync stays frame-accurate. |
| `outro_audio` | String | *(unset)* | Audio played **after** the narration concludes. |
| `title_image` | String | *(unset)* | Fallback location for `video.title_image`. |
| `title_duration` | Float | `3.0` | Fallback location for `video.title_duration`. |
| `outro_image` | String | *(unset)* | Fallback location for `video.outro_image`. |
| `outro_start` | Float | `0.0` | Fallback location for `video.outro_start`. |

```yaml
bumpers:
  intro_audio: "assets/intro.mp3"   # subtitles shift automatically by its duration
  outro_audio: "assets/outro.mp3"
```

> [!NOTE]
> Background music is **not** a bumper — it lives at `audio.background_music`. The
> bumper stage only runs if at least one of these files actually exists on disk.

---

## 📺 4c. The `publishing` Block (YouTube Upload & Metadata)

Controls both automated uploading and the offline drag-and-drop package. Full setup
instructions are in the **[Publishing Guide](publishing_guide.md)**.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `platform` | String | `"youtube"` | Target platform. Only `youtube` is implemented. |
| `enabled` | Boolean | `false` | Turns on automated uploading. Requires a Google key file. |
| `generate_offline_package` | Boolean | `true` | Builds `YouTube_Upload_Package/` folders containing the video, thumbnail and a ready-to-paste `metadata.txt`. |
| `client_secrets_file` | String | `"~/.vidx/client_secrets.json"` | Your Google application key. Identifies the *app*, not the channel. |
| `token_file` | String | `<manifest folder>/youtube_token.json` | Cached channel login. Identifies **which channel receives the videos**. Point two projects at one file to deliberately share a channel. |
| `privacy_status` | String | `"unlisted"` | `private`, `unlisted`, or `public`. Not validated — a typo uploads with YouTube's own default. |
| `category_id` | String | `"22"` | YouTube category. `22` = People & Blogs, `27` = Education. |
| `playlist_name` | String | `""` | Playlist to file videos into. Found by name, or created if absent. |
| `title_template` | String | `"{book} Chapter {chapter:02d} — {language} Audio Bible"` | Video title. See placeholders below. |
| `description_template` | String | *(multi-line default)* | Video description. Accepts the same placeholders. |
| `tags` | List | `["AudioBible", "Scripture", "{language}", "{book}"]` | Each tag is resolved individually. |

### Template Placeholders

`{book}`, `{chapter}`, `{language}`, `{text_copyright}`, `{audio_copyright}`.

`{chapter}` is a real integer, so `{chapter:02d}` gives `01`, `02`. Unknown placeholders
are left as literal text rather than raising an error, which makes typos easy to miss —
check your first rendered title.

The last three come from the `project` block, **not** from `publishing`:

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `project.language` | String | `"Language"` | Fills `{language}`. Set this or every title says "Language". |
| `project.text_copyright` | String | `""` | Fills `{text_copyright}`. |
| `project.audio_copyright` | String | `""` | Fills `{audio_copyright}`. |

```yaml
project:
  language: "Sindhi"
  text_copyright: "© 2024 Bible Society"
  audio_copyright: "© 2024 Recording Ministry"

publishing:
  platform: "youtube"
  enabled: true
  privacy_status: "unlisted"
  playlist_name: "Gospel of Mark — Sindhi Audio Bible"
  title_template: "{book} Chapter {chapter:02d} — {language} Audio Bible"
```

> [!NOTE]
> `publish_manifest.json` is written whenever **either** `enabled` **or**
> `generate_offline_package` is true — and the latter defaults to `true`. To produce
> no publishing artifacts at all, set both to `false`.

---

## 🎨 5. The `style` Block (Typography, Colors & Transparency)

The `style` block controls the visual appearance of Scripture verses, section headings (`\s1`), and inline verse references (`1:1`).

### 5.1 Hex Colors and Alpha / Transparency
VIDX supports standard CSS hexadecimal color formatting:
*   **6-Digit Hex (`#RRGGBB`):** Standard RGB color (e.g., `#FFFFFF` for white, `#FFD400` for gold).
*   **8-Digit Hex (`#RRGGBBAA`):** RGB + Alpha opacity channel, where `AA` ranges from `00` (fully transparent) to `FF` (fully opaque). Example: `#000000A0` creates a dark, semi-transparent black.

> [!NOTE]
> Under the hood, VIDX automatically converts standard CSS hex colors and alpha opacity values into Advanced SubStation Alpha (`&HAABBGGRR`) format, ensuring exact color matching across FFmpeg and standalone media players.

### 5.2 Configurable Background Box Transparency
For optimal readability against busy background videos, you can enable a solid or semi-transparent background box behind subtitles using `background_box: true`. You can fine-tune its transparency using either `background_opacity` or `background_transparency`:

```yaml
style:
  verse:
    background_box: true
    background_color: "#000000"
    # Specify opacity as a decimal (0.0 to 1.0) or integer percentage (0 to 100):
    background_opacity: 0.65       # 65% opaque black box (35% transparent)
    # Alternatively, specify transparency directly:
    # background_transparency: 40  # 40% transparent box (60% opaque)
```

### 5.3 Numpad Alignment Grid & Margins
Subtitle alignment uses the standard 1-9 numpad grid layout:

```
[7] Top-Left       [8] Top-Center       [9] Top-Right
[4] Middle-Left    [5] Middle-Center    [6] Middle-Right
[1] Bottom-Left    [2] Bottom-Center    [3] Bottom-Right
```

*   **Standard Landscape (`alignment: 2`):** Position verses at bottom-center with `margin_bottom: 60` and side margins `margin_lr: 60`.
*   **Mobile Reels / Shorts Safety Zone (`margin_bottom: 140+`):** Vertical videos played on TikTok, YouTube Shorts, or Instagram Reels have UI overlays (captions, like buttons, profile icons) along the bottom and right edges. **Always set `margin_bottom: 140` (or up to `180`) and `margin_lr: 45` on vertical builds** to prevent scripture text from being obscured by app UI elements!

### 5.4 Comprehensive Style Parameters

```yaml
style:
  verse:
    font: "Bailey"              # Typography font family name
    size: 50                    # Font size in points (e.g., 50 for 1080p, 90 for 4K)
    color: "#FFFFFF"            # Primary lyric text color
    outline_color: "#000000"    # Character border outline color
    outline_width: 3            # Border thickness in pixels
    shadow: 1                   # Drop shadow offset in pixels
    alignment: 2                # Numpad alignment (2 = Bottom-Center)
    margin_bottom: 60           # Distance from bottom screen edge
    margin_lr: 60               # Left and right lateral safety margins
    background_box: true        # Enable background readability box
    background_color: "#000000" # Base color for background box
    background_opacity: 0.60    # Opacity level (0.60 = 60% opaque)

  heading:
    font: "Bailey"
    size: 60                    # Typically 15-20% larger than verse font
    color: "#FFD400"            # Accent color (e.g., Gold/Yellow)
    outline_color: "#000000"    # Border outline color
    outline_width: 3            # Border thickness; defaults to the verse value
    shadow: 1                   # Drop shadow offset; defaults to the verse value
    alignment: 8                # Top-Center positioning
    margin_vertical: 80         # Distance from top edge
    hold_seconds: 20            # Keep the heading up this long (see 5.6); unset = read time only
    bold: true                  # Render headings in bold weight
    background_box: true        # Headings support the same readability box as verses
    background_color: "#000000"
    background_opacity: 0.60

  verse_number:
    show: true                  # Display inline verse references (e.g., "1:1")
    color: "#FFC080"            # Accent color for verse numbers
    size: 38                    # Typically 75% of verse font size
    on_every_segment: false     # If false, only shows reference on first segment (e.g., 1a, not 1b)
    # Note: verse numbers have no font/alignment/margin keys of their own -- they are
    # drawn inline with the verse text and inherit its style and position.

  overlay:
    enabled: true
    title: true                 # Automatically derives title from book and chapter (or override per job)
    title_color: "#FFFFFF"      # Color for chapter heading/title
    title_position: 5           # ASS alignment (5 = Middle-Center, 8 = Top-Center)
    subtitle: "AUDIO BIBLE"     # Subtitle text displayed below title
    subtitle_position: 5        # Alignment for subtitle text
    watermark_text: "BRAND"     # Text watermark rendered onto video
    watermark_position: 4       # Alignment (4 = Middle-Left, 7 = Top-Left)
    watermark_opacity: 0.50     # Opacity float (0.50 = 50% opacity)
    opacity: 0.50               # General overlay opacity fallback
    divider_line: true          # Draw horizontal divider line between title and subtitle
    branding_text: "MINISTRY"   # Third text line, for a ministry or channel name
    duration: "full"            # Seconds to display, or "full" for the whole video
```

> [!NOTE]
> The `overlay` block accepts far more than the common keys above. Every text element
> — `title`, `subtitle`, `branding`, `watermark`, `divider` — takes its own
> `_font`, `_size`, `_color`, `_opacity`, `_transparency`, `_alignment` (or `_position`)
> and `_margin_v` suffix, e.g. `subtitle_font`, `branding_margin_v`, `watermark_size`.
> Anything you leave out is derived from the verse and heading styles. `overlay` may
> also be written as a **top-level block** instead of under `style`.

### 5.5 ASS Numpad Alignment Reference
When configuring positioning (`alignment`, `title_position`, `watermark_position`), VIDX uses standard ASS numeric layout (similar to a keyboard numpad):
*   **7**: Top-Left | **8**: Top-Center | **9**: Top-Right
*   **4**: Middle-Left | **5**: Middle-Center | **6**: Middle-Right
*   **1**: Bottom-Left | **2**: Bottom-Center | **3**: Bottom-Right

> [!WARNING]
> libass ignores `MarginV` for the middle alignments (**4**, **5**, **6**). Two elements
> at alignment 5 render on top of each other and no margin key will separate them — give
> one of them a top or bottom alignment instead.

### 5.6 Holding Section Headings On Screen (`hold_seconds`)

A `\s` heading is timed for as long as the narrator reads it, often only 1–2 seconds, so it
flashes past while the section it introduces runs for minutes. `heading.hold_seconds` keeps
it up longer:

```yaml
style:
  heading:
    alignment: 2                # bottom-centre, out of the verse block's way
    margin_vertical: 330
    hold_seconds: 20            # or "full" for no time limit
```

*   The **next heading's start always wins**, so two headings never overlap. A section shorter
    than `hold_seconds` hands off early — set `hold_seconds: "full"` and there is always
    exactly one heading on screen, changing at each section break.
*   The last heading in a chapter is capped at the end of the final timing row.
*   A hold **shorter** than the narrated read is ignored; the timing row wins.
*   Unset (the default) means no change: heading start and end come straight from the timing row.

Because the held heading now coexists with verses, give it an `alignment` and `margin_vertical`
that clear the verse block — the default top-centre works, but so does sitting it just above
the verses.

---

## 📦 6. The `jobs` Block (Single Chapter vs. Bulk Processing)

The `jobs` block defines the batch queue. Each item in the list represents a single conversion job pairing a USFM Scripture source, a timing map, and an audio soundtrack.

### 6.1 How USFM Chapter Matching Works
VIDX includes an integrated USFM 3.0 parser (`vidx.usfm_parser`) that **automatically identifies and extracts the target chapter matching the timing file**. 

Because of this intelligent matching, **you do not need to split USFM files by chapter**. You can point dozens or hundreds of chapter jobs to a single book-level USFM file (e.g., `42MRKsnd.SFM` or `58PHMMAL.SFM`), and VIDX will automatically extract the correct text for each timing map!

### 6.2 Single Chapter Setup
For simple or one-off renders, list a single job entry:

```yaml
jobs:
  - usfm: "src/mal/58PHMMAL10RO.SFM"
    timing: "src/mal/C01-57-PHM-01-timing.txt"
    audio: "src/mal/phm/01.mp3"
    output: "output/Philemon_Chapter_01.mp4"
```

### 6.3 Book-Level Bulk Processing (e.g., Gospel of Mark 1–16)
To process an entire book in a single unattended batch run, list all chapter timing and audio pairs under `jobs`, pointing them to the shared book `.SFM` file:

```yaml
jobs:
  - usfm: "src/snd/42MRKsnd.SFM"
    timing: "src/snd/timings/MRK_01_timing.txt"
    audio: "src/snd/audio/01.mp3"
    output: "output/Mark/Mark_01.mp4"

  - usfm: "src/snd/42MRKsnd.SFM"
    timing: "src/snd/timings/MRK_02_timing.txt"
    audio: "src/snd/audio/02.mp3"
    output: "output/Mark/Mark_02.mp4"

  # ... continue through Chapter 16 ...
```

### 6.4 Multi-Book / Entire New Testament Processing
When processing massive corpora like an entire New Testament (260 chapters), organize your `output` paths into clear book subdirectories to maintain clean archives:

```yaml
jobs:
  # Gospel of Matthew
  - usfm: "src/nt/01MAT.SFM"
    timing: "src/nt/mat/01_timing.txt"
    audio: "src/nt/mat/01.mp3"
    output: "output/New_Testament/01_Matthew/Matthew_01.mp4"

  # Gospel of Mark
  - usfm: "src/nt/02MRK.SFM"
    timing: "src/nt/mrk/01_timing.txt"
    audio: "src/nt/mrk/01.mp3"
    output: "output/New_Testament/02_Mark/Mark_01.mp4"
```

### 6.5 Per-Job Overrides
You can override global `video` settings on a **per-chapter basis** directly inside an individual job entry! Supported overrides include:

| Override Key | Description | Example |
| :--- | :--- | :--- |
| `background` | Overrides the default `background_media` for this specific chapter. | `background: "src/backgrounds/waterfall.mp4"` |
| `background_music` | Overrides default background music track for this specific chapter (`"none"` disables music). | `background_music: "src/audio/piano_ch1.mp3"` |
| `background_music_volume` | Overrides the background music volume level for this chapter. | `background_music_volume: 0.15` |
| `duration` | Limits rendering to `N` seconds (useful for quick chapter testing). | `duration: 15` |
| `keep_ass` | Override intermediate subtitle retention (`true` / `false`). | `keep_ass: true` |
| `watermark` | Per-chapter watermark. An **image path** (`.png`/`.jpg`/`.jpeg`/`.bmp`/`.gif`/`.svg`) is burned in by FFmpeg; any other string becomes overlay *text*. | `watermark: "src/logo.png"` |
| `title` | Overrides `overlay.title` for this chapter only. | `title: "The Passion Narrative"` |
| `book` | USFM book code. Normally auto-detected from the timing file's `\id`, then the USFM. Set it when detection fails. | `book: MRK` |
| `chapter` | Chapter number. Auto-detected from `\c`, then from the output/timing/audio filename. | `chapter: 5` |
| `output` | Output video path. Defaults to `<project.output_dir>/<audio filename>.mp4`. | `output: "output/Mark_01.mp4"` |

> [!NOTE]
> `usfm`, `timing` and `audio` are **required** in every job. If any one of them is
> missing the job is skipped silently, which usually looks like "VIDX rendered fewer
> chapters than I listed".

#### Example: Bulk Run with Per-Chapter Backgrounds & Music
```yaml
jobs:
  - usfm: "src/snd/42MRKsnd.SFM"
    timing: "src/snd/MRK_01_timing.txt"
    audio: "src/snd/01.mp3"
    output: "output/Mark_01.mp4"
    background: "src/backgrounds/desert_sunrise.mp4"  # Custom background for Ch 1
    background_music: "src/audio/gentle_piano.mp3"    # Custom music track
    background_music_volume: 0.12

  - usfm: "src/snd/42MRKsnd.SFM"
    timing: "src/snd/MRK_02_timing.txt"
    audio: "src/snd/02.mp3"
    output: "output/Mark_02.mp4"
    background: "src/backgrounds/sea_of_galilee.mp4"  # Custom background for Ch 2
    background_music: "none"                          # Disable background music for Ch 2
```

---

## ⚡ 7. Dual-Purpose Subtitle Generation Mode (No Video)

VIDX can serve a dual purpose as a high-speed batch subtitle generator. If your field team only needs `.srt` or `.ass` subtitle files (for importing into Premiere Pro, DaVinci Resolve, or YouTube closed captions) without rendering MP4 videos, enable **Subtitle Only Mode**.

### Option A: Enable via YAML Configuration
Set `generate_only: true` and specify your desired `subtitle_format` (`"srt"`, `"ass"`, or `"both"`):

```yaml
project:
  name: "Gospel of Mark - Subtitle Extraction"
  output_dir: "output/subtitles"
  generate_only: true          # Bypasses FFmpeg video rendering
  subtitle_format: "both"      # Generates both .srt and .ass files simultaneously

jobs:
  - usfm: "src/snd/42MRKsnd.SFM"
    timing: "src/snd/MRK_01_timing.txt"
    audio: "src/snd/01.mp3"
    output: "output/subtitles/Mark_01"  # Extensions (.srt / .ass) appended automatically
```

Run the batch:
```bash
vidx -c subtitles_config.yaml
```

### Option B: Enable via CLI Flags
You can trigger subtitle-only mode on any existing YAML config or single-file command using CLI flags:

```bash
# Generate both SRT and ASS for an entire batch YAML project without rendering video
vidx -c project_16x9.yaml --generate-only --format both

# Generate an SRT file for a single chapter directly from command line
vidx --usfm src/snd/42MRKsnd.SFM --timing src/snd/MRK_01_timing.txt --generate-only --format srt -o output/Mark_01.srt
```

> [!TIP]
> In `--generate-only` mode, **audio file verification is bypassed**. You can generate perfect SRT and ASS subtitle files even if the audio soundtrack files are missing or haven't been downloaded yet!

---

## 📑 8. Copy-Paste Production Templates

### Template A: Standard 16:9 Landscape Widescreen (1080p)
```yaml
project:
  name: "Standard 16x9 Release"
  output_dir: "output/16x9"
  generate_only: false

video:
  resolution: "1920x1080"
  fps: 24
  codec: "libx264"
  preset: "fast"
  crf: 22
  background_media: "src/backgrounds/landscape_loop.mp4"
  loop_background: true
  scaling_mode: "pad"

style:
  verse:
    font: "Bailey"
    size: 50
    color: "#FFFFFF"
    outline_color: "#000000"
    outline_width: 3
    shadow: 1
    alignment: 2
    margin_bottom: 60
    margin_lr: 60
    background_box: true
    background_color: "#000000"
    background_opacity: 0.60

  heading:
    font: "Bailey"
    size: 60
    color: "#FFD400"
    alignment: 8
    margin_vertical: 80
    bold: true

  verse_number:
    show: true
    color: "#FFC080"
    size: 38
    on_every_segment: false

jobs:
  - usfm: "src/book.SFM"
    timing: "src/chapter_01_timing.txt"
    audio: "src/chapter_01.mp3"
    output: "output/16x9/Chapter_01.mp4"
```

---

### Template B: Vertical Mobile Shorts / Reels (9:16) with UI Safety Margins
```yaml
project:
  name: "Vertical Shorts 9x16 Release"
  output_dir: "output/9x16"

video:
  resolution: "1080x1920"
  fps: 30
  codec: "libx264"
  preset: "fast"
  crf: 22
  background_media: "src/backgrounds/vertical_loop.mp4"
  loop_background: true
  scaling_mode: "crop"          # Crops widescreen background to fill vertical canvas

style:
  verse:
    font: "Bailey"
    size: 48
    color: "#FFFFFF"
    outline_color: "#000000"
    outline_width: 3
    shadow: 2
    alignment: 2
    margin_bottom: 140          # Elevated bottom margin avoids TikTok/Reels UI overlay
    margin_lr: 45               # Narrow lateral margins for vertical screens
    background_box: true
    background_color: "#000000"
    background_opacity: 0.70    # Slightly darker box for mobile readability

  heading:
    font: "Bailey"
    size: 56
    color: "#FFD400"
    alignment: 8
    margin_vertical: 100
    bold: true

  verse_number:
    show: true
    color: "#FFC080"
    size: 36
    on_every_segment: false

jobs:
  - usfm: "src/book.SFM"
    timing: "src/chapter_01_timing.txt"
    audio: "src/chapter_01.mp3"
    output: "output/9x16/Chapter_01_Vertical.mp4"
```

---

### Template C: Batch Subtitle Extraction (SRT + ASS Only)
```yaml
project:
  name: "Complete Book Subtitle Extraction"
  output_dir: "output/subtitles"
  generate_only: true           # Skip video rendering
  subtitle_format: "both"       # Output both .srt and .ass

style:
  verse:
    font: "Bailey"
    size: 50
    color: "#FFFFFF"
    background_box: false

jobs:
  - usfm: "src/snd/42MRKsnd.SFM"
    timing: "src/snd/MRK_01_timing.txt"
    audio: ""                   # Audio not required in generate_only mode
    output: "output/subtitles/Mark_Chapter_01"

  - usfm: "src/snd/42MRKsnd.SFM"
    timing: "src/snd/MRK_02_timing.txt"
    audio: ""
    output: "output/subtitles/Mark_Chapter_02"
```

### Template D: Whole-Book Batch Processing with Parallel Workers
```yaml
project:
  name: "Gospel of Mark — Full Book Batch"
  output_dir: "output/mark_video_book"

video:
  resolution: "1920x1080"
  fps: 24
  codec: "libx264"
  preset: "fast"
  crf: 23
  background_media: "src/snd/bg.mp4"
  loop_background: true
  title_card: "assets/title.jpg"
  title_duration: 4.0

audio:
  codec: "aac"
  bitrate: "192k"
  background_music: "assets/bgm.mp3"
  background_music_volume: 0.15

style:
  verse:
    font: "Nirmala UI"
    size: 48
    color: "#FFFFFF"
    background_box: true
    background_opacity: 0.50

jobs:
  - usfm: "src/snd/42MRKsnd.SFM"
    timing: "src/snd/timings/MRK_01_timing.txt"
    audio: "src/snd/audio/01.mp3"
    output: "output/mark_video_book/Mark_01.mp4"

  - usfm: "src/snd/42MRKsnd.SFM"
    timing: "src/snd/timings/MRK_02_timing.txt"
    audio: "src/snd/audio/02.mp3"
    output: "output/mark_video_book/Mark_02.mp4"
```
*Run with 4 parallel CPU workers for maximum speed:*
```bash
vidx --config book_config.yaml -w 4
```
