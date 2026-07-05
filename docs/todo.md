# VIDX Project Roadmap & TODOs
> Tracking active milestones, future feature enhancements, and engineering requirements for the VIDX Scripture Video Generator.

---

## 🚨 Immediate Priorities (Next Steps)

- [ ] **GitHub Pages Documentation Site (`gh-pages` Deployment)**
  - [ ] Set up static documentation deployment (e.g., using MkDocs Material or Jekyll / GitHub Actions) to publish `docs/` and `README.md` to GitHub Pages.
  - [ ] Ensure user guides, configuration references, and tutorials are easily browsable by field coordinators and translation technicians online.
  - [ ] Add site navigation and search functionality for rapid troubleshooting.

- [ ] **Release `v0.2.0` (Self-Contained & Dual-Purpose Engine)**
  - [ ] Build standalone Windows executable (`vidx.exe`) using PyInstaller bundling the newly internalized `vidx.usfm_parser` and zero external Git dependencies.
  - [ ] Draft comprehensive GitHub Release notes highlighting:
    - **Dual-Purpose Subtitle Mode:** `--generate-only --format srt|ass|both` (and YAML `generate_only: true`).
    - **Self-Contained Architecture:** Internalized USFM 3.0 parser removing external Git requirements.
    - **Configurable Transparency:** Exact opacity decimals and transparency percentages for background readability boxes.
    - **Clean Workspace Hierarchy:** Introduction of `examples/` directory for multi-language templates.
  - [ ] Publish pre-compiled Windows executable and Python wheel artifacts to GitHub Release.

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

- [ ] **Title Cards & Video Thumbnail Support**
  - [ ] Enable users to specify a still title image (`video.title_card: "assets/title.jpg"`, `video.title_duration: 4.0`) that displays at the beginning of the video before scripture dialogue starts.
  - [ ] Ensure title cards are rendered at the exact target resolution (`1920x1080`, `1080x1920`, or `1080x1080`) so they can serve dual purpose as YouTube, Facebook, and Instagram video thumbnails.

- [ ] **Audio Intro & Outro Bumper Clips**
  - [ ] Add configuration options for introductory and concluding audio clips (`audio.intro_clip: "assets/intro.mp3"`, `audio.outro_clip: "assets/outro.mp3"`).
  - [ ] Implement automatic FFmpeg audio concatenation: play intro bumper -> play main AUDX scripture audio -> play outro credits bumper.
  - [ ] **Automatic Subtitle Timestamp Shifting:** When an intro clip is added, automatically offset all verse start/end timestamps in the `.ass`/`.srt` subtitle streams by the duration of the intro clip so scripture synchronization remains perfectly aligned!

- [ ] **Cloud & Streaming Platform Integration (YouTube / Vimeo One-Touch Publishing)**
  - [ ] **API Authentication & YAML Config:** Add optional publishing block (`publishing.platform: "youtube"`, OAuth client secrets, channel ID) for direct integration with YouTube Data API v3 and Vimeo API.
  - [ ] **One-Touch Upload (`--publish`):** Enable single-command or GUI button publishing that automatically uploads rendered `.mp4` video files to the designated channel immediately after generation.
  - [ ] **Automated Metadata & Thumbnails:** Automatically set video Title to scripture book and chapter, populate the video Description with verse ranges and translation copyright, attach tags (`#AudioBible`, `#Scripture`), and upload the generated `title_card.jpg` as the official video thumbnail!
  - [ ] **Playlist Organization:** Automatically organize uploaded chapter videos into book-level playlists (e.g., *"Gospel of Mark — Malayalam Translation"*).

---

## 🧪 Engineering & Methodology Requirements

- [x] **Comprehensive Automated Test Suite (`pytest`)**
  - [x] Built test suites covering `Config`, `USFMParser`, `TimingParser`, `TextSegmenter`, `SRTGenerator`, `ASSGenerator`, `FFmpegBuilder`, and `BatchRunner` (22 tests passing).
- [ ] **Test-Driven Development (TDD) Enforcement**
  - [ ] **Mandatory Rule:** All future feature developments, bug fixes, and refactoring **must** follow strict TDD workflow:
    1. Write a failing test in `tests/` capturing the desired behavior or bug reproduction.
    2. Implement minimal production code to pass the test.
    3. Refactor while ensuring all 22+ tests remain green.

---

## 🚀 Future Enhancements & Roadmap

### 1. CI/CD & Automation
- [ ] **GitHub Actions CI Pipeline:**
  - Automatically run `pytest` across Python 3.8, 3.10, and 3.12 on every push and pull request.
  - Automate linting and formatting verification.
- [ ] **Automated Release Builder:**
  - Create a GitHub Actions workflow triggered by version tags (e.g., `v0.2.0`) to automatically compile PyInstaller executables across Windows and Linux, attaching them to the GitHub Release page.

### 2. Video & Audio Rendering Enhancements
- [ ] **Audio Fade-in / Fade-out:**
  - Add optional YAML configuration (`audio.fade_in_sec`, `audio.fade_out_sec`) to apply smooth audio transitions at chapter boundaries using FFmpeg `afade` filter.
- [ ] **Video Loop Crossfading:**
  - Implement smooth video crossfade transitions when looping short background video clips to eliminate visual jumps at loop seam points.
- [ ] **Custom Watermarks & Channel Logos:**
  - Enable placing station or organization logos (PNG with alpha) in any corner of the video via YAML config (`video.watermark: "assets/logo.png"`).

### 3. Typography & Internationalization
- [ ] **Font Fallback Validation:**
  - Create an automated CLI pre-flight check that verifies required fonts (e.g., `Bailey`, `Nirmala UI`, `Mangal`) are installed on the OS before launching long FFmpeg render queues.
- [ ] **Right-to-Left (RTL) Script Optimization:**
  - Add specific regression test cases and layout presets for Arabic, Urdu, and Hebrew scripture rendering.

### 4. Bulk Processing & Performance
- [ ] **Multi-Worker Memory Profiling:**
  - Optimize memory footprint during large concurrent batch runs (`-w 4` or `-w 8`) when processing entire New Testament (NT) audio libraries (260+ chapters).
- [ ] **Multi-Worker Live Progress Bars (`rich` / `enlighten` / `tqdm`):**
  - [ ] **Decoupled GUI-Ready Callback Architecture (Observer Pattern):** **MANDATORY ARCHITECTURAL RULE:** Progress reporting must NOT be hardcoded to console prints or terminal UI libraries. Instead, implement an event/callback interface (`progress_callback(event: ProgressEvent)`) emitted by `FFmpegBuilder` and `BatchRunner`. Structured events (`job_id`, `worker_id`, `book`, `chapter`, `status`, `percent`, `speed`, `fps`, `elapsed`, `eta`) will allow both the CLI terminal observer and the upcoming GUI application to display live progress bars from the exact same backend engine!
  - [ ] **Dedicated Worker Mapping:** Display a live interactive progress bar for *each* parallel rendering worker (`-w WORKERS`), showing the exact scripture book, chapter, and file currently being processed (e.g., `[Worker 1] Mark Ch 05: 45% ━━━╸━━━━━━`).
  - [ ] **Live Rendering Metrics:** Report real-time FFmpeg encoding stats on the progress bar: current processing speed (e.g., `2.3x` real-time), encoded frames per second (`fps`), elapsed time, and estimated time of arrival (`ETA`).
  - [ ] **Global Batch Queue Summary:** Display a master progress bar tracking total completed chapters vs. remaining jobs across the entire New Testament conversion queue (`24 / 260 Chapters Completed [9%]`).

---

## ✅ Recently Completed Milestones (v0.2.0 Evolution)
- [x] **Internalized USFM Parser:** Migrated `usfm-converter` into `vidx.usfm_parser` to resolve Git dependency issues and simplify PyInstaller EXE builds.
- [x] **Dual-Purpose Subtitle Generator:** Enabled high-speed standalone subtitle extraction (`.srt` and `.ass`) without requiring video rendering or audio soundtrack files.
- [x] **Configurable Background Box Transparency:** Implemented fine-grained opacity and transparency controls (`background_opacity` / `background_transparency`).
- [x] **Repository Reorganization:** Overhauled `.gitignore` to industry standards, removed scratch artifacts, and consolidated multi-language configurations into clean `examples/` templates.
