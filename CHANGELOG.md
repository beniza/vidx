# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.3] - 2026-08-03

### Added
- **`scripts/benchmark_align.py`:** aligns a whole book chapter by chapter with a progress bar, then reports per-chapter speed and scores verse boundaries against the SAB reference timings. Previously this was done by hand one chapter at a time; run it after any change to `vidx/align.py`.

### Fixed
- **Last Verse Ran to the End of the Audio File:** `--align` set the final segment's end time to the audio duration, so any trailing silence, closing announcement, or outro music held the last verse's subtitle on screen. Measured on Philemon 1 this overshot by 7.0s and on Malayalam Mark 16 by 11.3s. The end now comes from the last aligned character's frame, i.e. where the narration of the text actually stops. Cross-checked against the narrator's measured speaking rate on Mark 16 (128 characters at ~11 chars/s predicts a 213.4s end): the new value lands at 214.5s, within 1.1s, while the old value was 12.4s late. Note that SAB's own timing files *do* pad the last verse over closing audio (218.8s for the same verse), so a VIDX-generated file will legitimately end earlier than the SAB equivalent.

## [0.4.2] - 2026-08-03

### Fixed
- **uroman Data Bundling in Executable:** Updated `vidx.spec` to include `uroman` submodules and data files in PyInstaller builds. Without this, the distributed `.exe` would fail with "Cannot open file" errors when attempting to romanize text for alignment, causing `--align` to crash with "No alignable text after romanization." This affected timing file generation on end-user computers.

## [0.4.1] - 2026-08-03

### Fixed
- **GitHub Actions Release Workflow:** Updated to install both optional extras (`youtube` and `align`) before building the Windows executable, ensuring the distributed `.exe` includes full support for timing generation and YouTube publishing without requiring a separate Python environment.

## [0.4.0] - 2026-08-03

### Added
- **Timing File Generation via Forced Alignment (`--align`):** VIDX can now produce SAB-compatible timing files directly from audio + USFM, removing the hard dependency on Scripture App Builder (or aeneas) for teams that don't already have timing data. Uses Meta's MMS-300M-1130 aligner (Wav2Vec2 CTC, 1130+ languages) via ONNX Runtime — no PyTorch — with `uroman` romanization so it is script-agnostic. Ships as the optional `vidx[align]` extra; the ~340MB INT8 model is fetched at runtime to `~/.vidx/mms-aligner/` and is never bundled (it is CC-BY-NC 4.0, unlike VIDX's MIT licence).
- **Phrase-Level Alignment (`--level phrase`):** splits verses at punctuation into `1a`/`1b`/`1c` segments matching SAB's phrase-level timing convention.
- **Section Heading Timings:** `\s` headings are emitted as `s1`/`s2`/... segments (SAB convention) since narrators read them aloud; measured on Sindhi Mark 5 this moved p90 error from 1.13s to 0.52s. Disable with `--no-headings`.
- **Audacity Label Round-Trip (`--to-labels` / `--from-labels`):** a timing file body is already an Audacity label track, so fine-tuning needs no bespoke editor — export, drag boundaries against the waveform, merge back.
- **`docs/alignment_guide.md`:** end-user walkthrough for timing generation, including the Audacity fine-tuning loop, accuracy figures, and troubleshooting.
- **`docs/build-explainer.ps1`:** records the previously-undocumented pandoc/XeLaTeX invocation for the explainer PDF. The build requires `--shift-heading-level-by=-1`; without it `###` becomes `\subsubsection`, which the template has no format for, and the build fails.

### Documentation
- **Optional extras were never documented.** Neither `pip install vidx[youtube]` nor the `align` extra appeared anywhere in the docs, so following the publishing guide end-to-end produced `No module named 'google'` at the final step. Added an "Optional Extras" table to the README and a mandatory **Step 0** to the publishing guide, plus a troubleshooting entry covering the split-interpreter case.
- **YouTube channel credentials:** documented the distinction between `client_secrets.json` (identifies the app) and `youtube_token.json` (identifies the channel), Brand Account selection, publishing to multiple channels, and how to switch channels. Added a full `publishing:` config key reference — `token_file` was implemented but undocumented.
- **`vidx.spec` bundling trap:** `collect_submodules('google.auth')` returns an empty list without error when the extra is absent, silently producing an `.exe` that fails at runtime. Documented the need to build with the extra installed and to test the artifact before distribution.
- **Explainer PDF** rewritten to reflect that a Scripture App is no longer a prerequisite, with new sections on generating timing files and publishing to YouTube.
- Added `getting_started.md`, `alignment_guide.md`, and `publishing_guide.md` to the MkDocs nav — the publishing guide was previously absent from the docs site entirely.

### Fixed
- **Explainer PDF running header** printed `VIDX --- Turn Your...` as three literal hyphens; fontspec/XeTeX does not apply TeX dash ligatures, so the template now uses a real em dash.

## [0.3.4] - 2026-07-14

### Added
- **Luke, John & Acts (Sindhi Audio Bible):** batch configs, USFM source, timing data, and channel logo for three new GPU-rendered production books.
- **Per-Manifest YouTube Token Caching:** `--manifest` publishing now defaults the OAuth token cache to `<manifest's folder>/youtube_token.json` instead of the global `~/.vidx/youtube_token.json`, so publishing to multiple projects/channels no longer clobbers a shared login.
- **`docs/session_summary.md` and expanded `docs/todo.md`:** logged production findings (YouTube quota mechanics, GPU worker-count scaling, timing-data validation idea) as actionable follow-ups.

### Fixed
- **Background Video Audio Leakage:** background clips are now demuxed with `-an` so their own audio track can never bleed into the output, regardless of which render branch (watermark/title/outro vs. plain) runs.
- **Batch Summary Reporting Clobbered by Live Progress Display:** `run_all()`'s summary tables and "Total Elapsed" wall-clock panel were being printed while the Rich live progress display was still active, so the output was overwritten for any multi-chapter batch. Extracted into `BatchRunner.print_summary()`, now called only after the progress display stops.
- **`john.yaml` Subtitle Position Typo:** `fsubtitle_position` (should be `subtitle_position`) was silently falling back to the wrong default overlay alignment.
- **Verse Segmentation Fallback:** `TextSegmenter` now falls back to standard/Arabic/Sindhi punctuation separators when none are supplied by the timing file, instead of producing a single unsplit segment.

## [0.3.3] - 2026-07-06

### Fixed
- **PyInstaller Google API Bundling:** Fixed runtime `ImportError` when running `--manifest` on end-user computers without Python installed by collecting all `google.auth`, `google.oauth2`, `google_auth_httplib2` submodules and all 582 JSON discovery data files in `vidx.spec`.
- **Error Diagnostics:** Updated `youtube.py` and `cli.py` to capture and display explicit import error messages instead of generic installation instructions when API dependencies fail to load.

## [0.3.2] - 2026-07-06

### Added
- **Complete Quickstart & Distribution Guide:** Added comprehensive user onboarding documentation (`docs/getting_started.md` and `docs/publishing_guide.md`) covering the entire VIDX workflow from generation to YouTube publishing in plain language.
- **Automatic Publishing Retry:** Enabled automatic retry for previously failed manifest items (`status: FAILED`) when re-running `vidx --manifest`.
- **Robust PyInstaller Spec:** Updated `vidx.spec` with complete submodule collection for character encoding (`charset_normalizer`/`chardet`) and Google API libraries, eliminating runtime dependency warnings in standalone executables.

## [0.3.1] - 2026-07-06

### Added
- **Dynamic ASS Overlays & Positioning:** Added support for custom positioning, alignment, opacity, and color configuration for overlay titles, subtitles, watermarks, and headings (`style.overlay`).
- **Job-Level Overrides:** Enabled job-level overrides for audio, background video, and background music in batch configurations.

### Fixed
- **USFM Chapter Isolation:** Fixed USFM verse extraction logic to properly isolate target chapters when internal `\c` tags are missing or when rendering multi-chapter batches.
- **Title and Heading Defaults:** Changed default overlay title color to clean white (`#FFFFFF`) and fixed position alignment handling.

## [0.3.0] - 2026-07-06

### Added
- **Hardware GPU Acceleration:** Added support for NVIDIA NVENC and Intel QSV encoding (`--gpu` flag and `video.gpu` YAML parameter).
- **Automatic Preprocessing & Loop Caching:** Auto-downscale 4K media to 1080p (`*_1080p.mp4`) and crossfade background loops (`*_xf1.0s.mp4`) before batch rendering to eliminate CPU bottlenecks.
- **Custom Watermarks & Channel Logos:** Configurable corner logos with position, margin, scale, and opacity (`video.watermark`).
- **Smooth Audio Transitions:** Configurable fade-in (`audio.fade_in_sec`) and fade-out (`audio.fade_out_sec`) durations.
- **YouTube API v3 Integration Plan:** Documented architectural plan for automated distribution in `docs/yt_integration_plan.md`.

### Changed
- **Rebranded:** Rebranded from `usfm2vdo` to `vidx` across all commands, module paths, and documentation.
- **Packaging:** Standardized on PEP 621 (`pyproject.toml`) as the single source of truth; removed legacy `setup.py`.
- **Licensing:** Added MIT License and repository legal declarations.

## [0.2.0] - 2026-07-01

### Added
- **Dual-Purpose Subtitle Extraction:** Generate standalone `.srt` and `.ass` subtitles at high speed without video rendering using `--generate-only --format srt|ass|both`.
- **Self-Contained USFM 3.0 Parser:** Fully internalized scripture syntax parsing (`vidx.usfm_parser`) with zero external dependency requirements.
- **Fine-Grained Transparency Control:** Set exact background box opacity decimals (`0.0` to `1.0`) or percentage transparency (`0%` to `100%`).

## [0.1.0] - 2026-06-15

### Added
- Initial alpha release of CLI scripture video generation engine.
- Integration of USFM parser, timing map parser, and FFmpeg command builder.
- Support for verse text styling, bounding box transparency, and chapter batch rendering.
