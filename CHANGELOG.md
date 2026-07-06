# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
