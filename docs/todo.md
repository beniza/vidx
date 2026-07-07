# VIDX Project Roadmap & TODOs
> Tracking active milestones, future feature enhancements, and engineering requirements for the VIDX Scripture Video Generator.

---

## 🚨 Immediate Priorities (Next Steps)

- [x] **GitHub Pages Documentation Site (`gh-pages` Deployment)** — *live at https://beniza.github.io/vidx/*
  - [x] Set up static documentation deployment (e.g., using MkDocs Material or Jekyll / GitHub Actions) to publish `docs/` and `README.md` to GitHub Pages.
  - [x] Ensure user guides, configuration references, and tutorials are easily browsable by field coordinators and translation technicians online.
  - [x] Add site navigation and search functionality for rapid troubleshooting.

- [x] **Release `v0.2.0` (Self-Contained & Dual-Purpose Engine)** — *superseded by v0.3.2*
  - [x] Build standalone Windows executable (`vidx.exe`) using PyInstaller bundling the newly internalized `vidx.usfm_parser` and zero external Git dependencies.
  - [x] Draft comprehensive GitHub Release notes highlighting:
    - **Dual-Purpose Subtitle Mode:** `--generate-only --format srt|ass|both` (and YAML `generate_only: true`).
    - **Self-Contained Architecture:** Internalized USFM 3.0 parser removing external Git requirements.
    - **Configurable Transparency:** Exact opacity decimals and transparency percentages for background readability boxes.
    - **Clean Workspace Hierarchy:** Introduction of `examples/` directory for multi-language templates.
  - [x] Publish pre-compiled Windows executable and Python wheel artifacts to GitHub Release.

---

## 🖥️ User Experience & Graphical Interface (GUI)

- [ ] **Graphical User Interface (GUI) Config Editor**
  - [ ] Develop a user-friendly GUI application (e.g., desktop app using Tkinter/PyQt or a local web-based editor) for translation field teams who are unfamiliar with command-line tools or YAML syntax.
  - [ ] **Interactive File Browsers:** Visual file pickers to select USFM scripture files, audio recordings (.mp3/.wav/.mpeg), verse timing maps (.txt), and background video loops/images.
  - [ ] **Visual Color & Transparency Pickers:** Built-in color selection palettes with real-time sliders for background bounding box opacity (`0%` to `100% transparent`) and font outline width.
  - [ ] **Live Subtitle Previewer:** Render an instant visual mockup showing how scripture dialogue, gold section headings (`\s1`), and verse prefixes (`5:1`) will look over the selected background video without running full FFmpeg rendering jobs.
  - [ ] **One-Click Batch Execution:** Button to launch sequential or multi-worker (`-w 4`) rendering queues directly from the GUI with live progress reporting.

---

## 🎬 Multimedia Production Enhancements

- [x] **Title Cards & Video Thumbnail Support**
  - [x] Enable users to specify a still title image (`video.title_card: "assets/title.jpg"`, `video.title_duration: 4.0`) that displays at the beginning of the video before scripture dialogue starts.
  - [x] Ensure title cards are rendered at the exact target resolution (`1920x1080`, `1080x1920`, or `1080x1080`) so they can serve dual purpose as YouTube, Facebook, and Instagram video thumbnails.

- [x] **Audio Intro, Outro & Background Music (BGM) Bumpers**
  - [x] Add configuration options for introductory and concluding audio clips (`audio.intro_clip: "assets/intro.mp3"`, `audio.outro_clip: "assets/outro.mp3"`).
  - [x] Implement automatic FFmpeg audio concatenation: play intro bumper -> play main AUDX scripture audio -> play outro credits bumper.
  - [x] **Looped Background Music Blending:** Allow specifying background music (`audio.background_music: "assets/bgm.mp3"`) with volume control (`audio.background_music_volume: 0.15`). Automatically loop the music continuously to match the scripture reading and seamlessly blend without reducing the narrator's volume!
  - [x] **Automatic Subtitle Timestamp Shifting:** When an intro clip is added, automatically offset all verse start/end timestamps in the `.ass`/`.srt` subtitle streams by the duration of the intro clip so scripture synchronization remains perfectly aligned!

- [x] **Cloud & Streaming Platform Integration (YouTube One-Touch Publishing)** — *shipped; validated by publishing the full book of Matthew (Sindhi) to YouTube*
  - [x] **API Authentication & YAML Config:** Add optional publishing block (`publishing.platform: "youtube"`, OAuth client secrets, channel ID) for direct integration with YouTube Data API v3.
  - [x] **One-Touch Upload (`--publish`):** Enable single-command or GUI button publishing that automatically uploads rendered `.mp4` video files to the designated channel immediately after generation.
  - [x] **Automated Metadata & Thumbnails:** Automatically set video Title to scripture book and chapter, populate the video Description with verse ranges and translation copyright, attach tags (`#AudioBible`, `#Scripture`), and upload the generated `title_card.jpg` as the official video thumbnail!
  - [x] **Playlist Organization:** Automatically organize uploaded chapter videos into book-level playlists (e.g., *"Gospel of Mark — Malayalam Translation"*).
  - [ ] **Vimeo support:** Extend the publishing block to the Vimeo API (YouTube done; Vimeo still pending).

---

## 🧪 Engineering & Methodology Requirements

- [x] **Comprehensive Automated Test Suite (`pytest`)**
  - [x] Built test suites covering `Config`, `USFMParser`, `ASSGenerator`, `FFmpegBuilder`, `BatchRunner`, `CLI`, `Manifest`, `Bumpers`, `Progress`, and `YouTube` (~54 tests across 10 files).
- [ ] **Test-Driven Development (TDD) Enforcement**
  - [ ] **Mandatory Rule:** All future feature developments, bug fixes, and refactoring **must** follow strict TDD workflow:
    1. Write a failing test in `tests/` capturing the desired behavior or bug reproduction.
    2. Implement minimal production code to pass the test.
    3. Refactor while ensuring the full suite remains green.

---

## 🚀 Future Enhancements & Roadmap

### 1. CI/CD & Automation
- [x] **GitHub Actions CI Pipeline:** (`.github/workflows/tests.yml`)
  - [x] Automatically run `pytest` across Python 3.10, 3.11, and 3.12 on every push and pull request.
  - [x] Automate linting verification via `flake8`.
- [x] **Automated Release Builder:** (`.github/workflows/release.yml`)
  - [x] Version-tag-triggered (`v*`) workflow that builds the wheel, sdist, and Windows `vidx.exe` (PyInstaller) and attaches them to the GitHub Release.
  - [ ] **Linux executable:** currently Windows-only (`runs-on: windows-latest`); add a Linux PyInstaller build if demand arises.

### 2. Video & Audio Rendering Enhancements
- [x] **GPU Hardware-Accelerated Video Encoding:**
  - Add optional YAML configuration (`video.codec: "h264_nvenc"`, `video.hwaccel: "auto"`) to replace software encoding (`libx264`) with GPU hardware encoders (NVIDIA NVENC, Intel QuickSync, AMD AMF, Apple VideoToolbox).
  - Implement automatic startup detection via `ffmpeg -encoders` to dynamically select the best available GPU encoder on the user's machine, achieving 3x to 10x faster rendering speeds while falling back seamlessly to CPU encoding if no GPU is present.
- [x] **Audio Fade-in / Fade-out:**
  - Add optional YAML configuration (`audio.fade_in_sec`, `audio.fade_out_sec`) to apply smooth audio transitions at chapter boundaries using FFmpeg `afade` filter.
- [x] **Video Loop Crossfading:**
  - Implement smooth video crossfade transitions when looping short background video clips to eliminate visual jumps at loop seam points (`video.loop_crossfade_sec`).
- [x] **Custom Watermarks & Channel Logos:**
  - Enable placing station or organization logos (PNG with alpha) in any corner of the video via YAML config (`video.watermark` / `video.logo`).

### 3. Typography & Internationalization
- [ ] **Font Fallback Validation:**
  - Create an automated CLI pre-flight check that verifies required fonts (e.g., `Bailey`, `Nirmala UI`, `Mangal`) are installed on the OS before launching long FFmpeg render queues.
- [ ] **Right-to-Left (RTL) Script Optimization:**
  - Add specific regression test cases and layout presets for Arabic, Urdu, and Hebrew scripture rendering.

### 4. Bulk Processing & Performance
- [ ] **Multi-Worker Memory Profiling:**
  - Optimize memory footprint during large concurrent batch runs (`-w 4` or `-w 8`) when processing entire New Testament (NT) audio libraries (260+ chapters).
- [x] **Multi-Worker Live Progress Bars (`rich` / `enlighten` / `tqdm`):**
  - [x] **Decoupled GUI-Ready Callback Architecture (Observer Pattern):** **MANDATORY ARCHITECTURAL RULE:** Progress reporting must NOT be hardcoded to console prints or terminal UI libraries. Instead, implement an event/callback interface (`progress_callback(event: ProgressEvent)`) emitted by `FFmpegBuilder` and `BatchRunner`. Structured events (`job_id`, `worker_id`, `book`, `chapter`, `status`, `percent`, `speed`, `fps`, `elapsed`, `eta`) will allow both the CLI terminal observer and the upcoming GUI application to display live progress bars from the exact same backend engine!
  - [x] **Dedicated Worker Mapping:** Display a live interactive progress bar for *each* parallel rendering worker (`-w WORKERS`), showing the exact scripture book, chapter, and file currently being processed (e.g., `[Worker 1] Mark Ch 05: 45% ━━━╸━━━━━━`).
  - [x] **Live Rendering Metrics:** Report real-time FFmpeg encoding stats on the progress bar: current processing speed (e.g., `2.3x` real-time), encoded frames per second (`fps`), elapsed time, and estimated time of arrival (`ETA`).
  - [x] **Global Batch Queue Summary:** Display a master progress bar tracking total completed chapters vs. remaining jobs across the entire New Testament conversion queue (`24 / 260 Chapters Completed [9%]`).
- [x] **Automatic Background Preprocessing & 1080p Caching:**
  - [x] Automatically downscale 4K/high-res background video clips to 1080p (`*_1080p.mp4`) and apply loop crossfades (`*_xf1.0s.mp4`) in a pre-rendering cache pass to eliminate CPU decoding bottlenecks during parallel batch runs.

---

## ✅ Recently Completed Milestones (v0.2.0 → v0.3.2 Evolution)
- [x] **v0.3.2 Release & Standalone Distribution:** Shipped `vidx.exe` via PyInstaller (bundling the internalized `vidx.usfm_parser`, Google auth submodules, and discovery schemas) with GitHub Release notes and distribution guides — superseding the original `v0.2.0` milestone.
- [x] **YouTube One-Touch Publishing:** Direct YouTube Data API v3 integration with OAuth config, `--publish` upload, automated title/description/tags/thumbnail metadata, and book-level playlist organization — validated end-to-end by publishing the entire book of Matthew (Sindhi) in a single day.
- [x] **GPU Hardware Acceleration & Monitoring:** Autodetect NVIDIA NVENC and Intel QSV encoding with `--gpu` CLI flag and `video.gpu: true`, featuring real-time GPU time and usage tracking in live batch progress tables.
- [x] **Automatic Background Media Preprocessing & Loop Caching:** Automatically pre-scales 4K media down to 1080p and bakes seamless loop crossfades (`xfade`) before batch execution, avoiding multi-worker CPU decoding bottlenecks.
- [x] **Audio Transitions & Branding Overlays:** Implemented smooth audio fade-in/fade-out (`afade`) and custom corner watermarks/channel logos (`overlay` + RGBA alpha blending).
- [x] **Title Cards & Video Thumbnail Support:** Enabled still title image display at the beginning of videos (`video.title_card`, `video.title_duration`), serving double-duty as social media video thumbnails.
- [x] **Broadcast Audio Bumpers & Looped Background Music (BGM):** Added audio intro/outro jingle concatenation (`audio.intro_clip`, `audio.outro_clip`), automatic subtitle timestamp shifting, and continuous looped background music blending (`audio.background_music`, `audio.background_music_volume`) via FFmpeg `amix`.
- [x] **Robust USFM Marker Stripping Fix:** Solved cross-reference and footnote text bleeding into subtitles by upgrading regex rules in `usfm_parser` and `ass_generator` to handle word boundaries and extended formatting tags without trailing spaces (`\x-`, `\f+`, `\ex`, `\rq`).
- [x] **Decoupled GUI-Ready Progress Bar & Callback System:** Architected structured event reporting (`ProgressEvent`) across `FFmpegBuilder` and `BatchRunner` with real-time encoding stats (`speed`, `fps`, `ETA`), complete with a multi-worker terminal UI using `rich` and zero stdout scraping required for GUI applications.
- [x] **Internalized USFM Parser:** Migrated `usfm-converter` into `vidx.usfm_parser` to resolve Git dependency issues and simplify PyInstaller EXE builds.
- [x] **Dual-Purpose Subtitle Generator:** Enabled high-speed standalone subtitle extraction (`.srt` and `.ass`) without requiring video rendering or audio soundtrack files.
- [x] **Configurable Background Box Transparency:** Implemented fine-grained opacity and transparency controls (`background_opacity` / `background_transparency`).
- [x] **Repository Reorganization:** Overhauled `.gitignore` to industry standards, removed scratch artifacts, and consolidated multi-language configurations into clean `examples/` templates.
