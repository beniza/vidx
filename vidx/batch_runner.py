"""
Batch Runner Module for VIDX
Orchestrates multi-chapter conversion and video rendering jobs with progress logging
and intermediate file management.
"""

import time
import sys
import concurrent.futures
import subprocess
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Union, Any

from .ass_generator import convert_to_ass
from .ffmpeg_builder import FFmpegBuilder
from .config import Config
from .progress import ProgressReporter, ProgressEvent
from .manifest import (
    ManifestManager,
    ManifestEntry,
    resolve_metadata_template,
    generate_offline_package,
)


@dataclass
class Job:
    usfm_file: str
    timing_file: str
    audio_file: str
    output_file: str
    background_media: Optional[str] = None
    background_music: Optional[str] = None
    background_music_volume: Optional[float] = None
    watermark: Optional[Union[str, dict]] = None
    title: Optional[str] = None
    duration: Optional[float] = None
    keep_ass: bool = True
    book: Optional[str] = None
    chapter: Optional[int] = None
    status: str = "PENDING"
    error_msg: Optional[str] = None
    codec_used: Optional[str] = None
    used_gpu: bool = False
    render_time: float = 0.0


class BatchRunner:
    """Manages execution of multiple video rendering jobs."""

    def __init__(self, config: Optional[Config] = None, auto_yes: bool = False):
        self.config = config or Config()
        self.auto_yes = auto_yes
        self.jobs: List[Job] = []
        self.builder = FFmpegBuilder(self.config.raw_config)
        self.progress_reporter = ProgressReporter()

    def add_job(
        self,
        usfm_file,
        timing_file,
        audio_file,
        output_file,
        background_media=None,
        duration=None,
        keep_ass=True,
        background_music=None,
        background_music_volume=None,
        watermark=None,
        title=None,
        book=None,
        chapter=None,
    ):
        """Add a rendering job to the batch queue."""
        job = Job(
            usfm_file=str(usfm_file),
            timing_file=str(timing_file),
            audio_file=str(audio_file),
            output_file=str(output_file),
            background_media=str(background_media) if background_media else None,
            background_music=str(background_music) if background_music is not None and str(background_music).strip() != "" else None,
            background_music_volume=float(background_music_volume) if background_music_volume is not None else None,
            watermark=watermark,
            title=str(title) if title is not None else None,
            duration=duration,
            keep_ass=keep_ass,
            book=str(book) if book is not None else None,
            chapter=int(chapter) if chapter is not None else None,
        )
        self.jobs.append(job)
        return job

    def load_jobs_from_config(self):
        """Load jobs listed under 'jobs' section in YAML configuration."""
        jobs_cfg = self.config.get("jobs", [])
        if not isinstance(jobs_cfg, list):
            return

        default_bg = self.config.video.get("background_media", "")
        output_dir = Path(self.config.project.get("output_dir", "output"))

        for idx, item in enumerate(jobs_cfg):
            if not isinstance(item, dict):
                continue
            usfm_f = item.get("usfm")
            timing_f = item.get("timing")
            audio_f = item.get("audio")
            if not (usfm_f and timing_f and audio_f):
                continue

            out_f = item.get("output")
            if not out_f:
                # Default output name based on audio or timing filename
                base_name = Path(audio_f).stem
                out_f = str(output_dir / f"{base_name}.mp4")

            bg_media = item.get("background") or item.get("background_media") or default_bg
            bg_music = item.get("background_music") if "background_music" in item else item.get("bg_music")
            bg_vol = item.get("background_music_volume") if "background_music_volume" in item else item.get("bg_music_volume")
            wm = item.get("watermark")
            title_str = item.get("title")
            dur = item.get("duration", None)
            keep = item.get("keep_ass", True)
            book_str = item.get("book")
            chap_val = item.get("chapter")
            if chap_val is not None:
                try:
                    chap_val = int(chap_val)
                except ValueError:
                    chap_val = None

            self.add_job(
                usfm_f,
                timing_f,
                audio_f,
                out_f,
                background_media=bg_media,
                duration=dur,
                keep_ass=keep,
                background_music=bg_music,
                background_music_volume=bg_vol,
                watermark=wm,
                title=title_str,
                book=book_str,
                chapter=chap_val,
            )

    def _execute_single_job(self, job: Job, worker_id: int = 0):
        """Execute a single job: 1) generate ASS, 2) render FFmpeg."""
        start_t = time.time()
        job.status = "RUNNING"

        usfm_path = Path(job.usfm_file)
        timing_path = Path(job.timing_file)
        audio_path = Path(job.audio_file)
        out_path = Path(job.output_file)

        if not job.book or job.chapter is None:
            try:
                # 1. Check timing file first for exact chapter number or book
                if timing_path.exists():
                    with open(timing_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("\\id ") and not job.book:
                                job.book = line.split()[1]
                            elif line.startswith("\\c ") and job.chapter is None:
                                try:
                                    job.chapter = int(line.split()[1])
                                except ValueError:
                                    pass
                                if job.book and job.chapter is not None:
                                    break

                # 2. Check output, audio, and timing filenames for chapter number before checking shared USFM
                if job.chapter is None:
                    audio_name = Path(job.audio_file).name if job.audio_file else ""
                    m = (
                        re.search(r"(?:[_-]|\b)(?:Ch|Chapter|Chp|c)[_-]?(\d+)", out_path.name, re.IGNORECASE)
                        or re.search(r"[_-](\d{1,3})[_-]?(?:timing|\.txt|\.tsv|\b)", timing_path.name, re.IGNORECASE)
                        or re.search(r"(?:[_-]|\b)(?:Chapter|Ch|Chp)[_-]?(\d+)", timing_path.name, re.IGNORECASE)
                        or re.search(r"^(\d{1,3})(?:\s+|[_-]|\b)", audio_name)
                        or re.search(r"(?:[_-]|\b)(?:Ch|Chapter|Chp|c)[_-]?(\d+)", audio_name, re.IGNORECASE)
                    )
                    if m:
                        try:
                            job.chapter = int(m.group(1))
                        except ValueError:
                            pass

                # 3. Check USFM file for any remaining missing metadata (especially book name, or fallback chapter)
                if usfm_path.exists() and (not job.book or job.chapter is None):
                    with open(usfm_path, "r", encoding="utf-8", errors="ignore") as f:
                        for _ in range(50):
                            line = f.readline().strip()
                            if line.startswith("\\id ") and not job.book:
                                job.book = line.split()[1]
                            elif line.startswith("\\c ") and job.chapter is None:
                                try:
                                    job.chapter = int(line.split()[1])
                                except ValueError:
                                    pass
            except Exception:
                pass

        self.progress_reporter.emit(
            ProgressEvent(
                job_id=str(job.usfm_file),
                worker_id=worker_id,
                status="STARTING",
                percent=0.0,
                book=job.book,
                chapter=job.chapter,
                message="Starting job...",
            )
        )

        # Determine subtitle format and generate-only mode
        sub_format = getattr(self, "subtitle_format", None) or self.config.project.get(
            "subtitle_format", "ass"
        )
        sub_format = str(sub_format).lower().strip()
        gen_only = (
            getattr(self, "generate_only", False)
            or self.config.project.get("generate_only", False)
            or self.config.project.get("subtitle_only", False)
        )

        # Verify inputs exist
        if not usfm_path.exists():
            job.status = "FAILED"
            job.error_msg = f"USFM file not found: {usfm_path}"
            self.progress_reporter.emit(
                ProgressEvent(
                    job_id=str(job.usfm_file),
                    worker_id=worker_id,
                    status="ERROR",
                    percent=0.0,
                    book=job.book,
                    chapter=job.chapter,
                    message=job.error_msg,
                )
            )
            return job
        if not timing_path.exists():
            job.status = "FAILED"
            job.error_msg = f"Timing file not found: {timing_path}"
            self.progress_reporter.emit(
                ProgressEvent(
                    job_id=str(job.usfm_file),
                    worker_id=worker_id,
                    status="ERROR",
                    percent=0.0,
                    book=job.book,
                    chapter=job.chapter,
                    message=job.error_msg,
                )
            )
            return job
        if not gen_only and not audio_path.exists():
            job.status = "FAILED"
            job.error_msg = f"Audio file not found: {audio_path}"
            self.progress_reporter.emit(
                ProgressEvent(
                    job_id=str(job.usfm_file),
                    worker_id=worker_id,
                    status="ERROR",
                    percent=0.0,
                    book=job.book,
                    chapter=job.chapter,
                    message=job.error_msg,
                )
            )
            return job

        out_path.parent.mkdir(parents=True, exist_ok=True)
        ass_path = out_path.with_suffix(".ass")

        bumpers_cfg = self.config.raw_config.get("bumpers", {})
        audio_cfg = self.config.raw_config.get("audio", {})
        intro_audio = bumpers_cfg.get("intro_audio")
        outro_audio = bumpers_cfg.get("outro_audio")
        bg_music = (
            job.background_music
            if job.background_music is not None
            else (audio_cfg.get("background_music") or bumpers_cfg.get("background_music"))
        )
        if bg_music and str(bg_music).lower() in ["none", "false", "off", ""]:
            bg_music = None
        bg_vol = float(
            job.background_music_volume
            if job.background_music_volume is not None
            else (
                audio_cfg.get("background_music_volume")
                or bumpers_cfg.get("background_music_volume")
                or 0.15
            )
        )

        actual_audio = audio_path
        if (
            (intro_audio and Path(intro_audio).exists())
            or (outro_audio and Path(outro_audio).exists())
            or (bg_music and Path(bg_music).exists())
        ):
            from .bumpers import prepare_bumper_audio

            combined_audio_path = out_path.with_name(
                f"{out_path.stem}_with_bumpers.wav"
            )
            success_bump, intro_dur, total_dur = prepare_bumper_audio(
                main_audio=str(audio_path),
                output_audio=str(combined_audio_path),
                intro_audio=intro_audio,
                outro_audio=outro_audio,
                background_music=bg_music,
                bg_music_volume=bg_vol,
            )
            if success_bump:
                actual_audio = combined_audio_path
                if "bumpers" not in self.config.raw_config:
                    self.config.raw_config["bumpers"] = {}
                self.config.raw_config["bumpers"]["_calc_intro_duration"] = intro_dur

        self.progress_reporter.emit(
            ProgressEvent(
                job_id=str(job.usfm_file),
                worker_id=worker_id,
                status="EXTRACTING_SUBTITLES",
                percent=10.0,
                book=job.book,
                chapter=job.chapter,
                message="Generating subtitles...",
            )
        )

        # 1a. Generate SRT subtitles if requested
        if sub_format in ["srt", "both"]:
            srt_path = out_path.with_suffix(".srt")
            print(f"[*] Generating SRT subtitles: {srt_path.name}")
            from .usfm_parser import convert_to_srt

            srt_success = convert_to_srt(
                usfm_file=usfm_path,
                timing_file=timing_path,
                output_file=srt_path,
                config=self.config.raw_config,
            )
            if not srt_success or not srt_path.exists():
                job.status = "FAILED"
                job.error_msg = f"SRT generation failed for {srt_path}"
                self.progress_reporter.emit(
                    ProgressEvent(
                        job_id=str(job.usfm_file),
                        worker_id=worker_id,
                        status="ERROR",
                        percent=0.0,
                        book=job.book,
                        chapter=job.chapter,
                        message=job.error_msg,
                    )
                )
                return job

        # 1b. Generate ASS subtitles (required if rendering video, or if requested)
        if sub_format in ["ass", "both"] or not gen_only:
            print(f"[*] Generating ASS subtitles: {ass_path.name}")
            success = convert_to_ass(
                usfm_file=usfm_path,
                timing_file=timing_path,
                output_file=ass_path,
                config=self.config.raw_config,
                job_book=job.book,
                job_chapter=job.chapter,
                job_title=job.title,
                job_watermark=job.watermark,
            )
            if not success or not ass_path.exists():
                job.status = "FAILED"
                job.error_msg = f"Subtitle generation failed for {ass_path}"
                self.progress_reporter.emit(
                    ProgressEvent(
                        job_id=str(job.usfm_file),
                        worker_id=worker_id,
                        status="ERROR",
                        percent=0.0,
                        book=job.book,
                        chapter=job.chapter,
                        message=job.error_msg,
                    )
                )
                return job

        if gen_only:
            job.render_time = time.time() - start_t
            job.status = "SUCCESS"
            self.progress_reporter.emit(
                ProgressEvent(
                    job_id=str(job.usfm_file),
                    worker_id=worker_id,
                    status="COMPLETED",
                    percent=100.0,
                    book=job.book,
                    chapter=job.chapter,
                    message="Subtitles generated successfully.",
                )
            )
            return job

        # 2. Render video using FFmpeg
        print(f"[*] Rendering video: {out_path.name}")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        codec_req = self.config.video.get("codec", "libx264")
        job.codec_used = self.builder.detect_best_video_codec(codec_req)
        job.used_gpu = any(
            kw in job.codec_used.lower()
            for kw in ["nvenc", "qsv", "amf", "videotoolbox", "vaapi", "cuda", "omx"]
        )

        render_success, msg = self.builder.render(
            audio_file=actual_audio,
            subtitle_file=ass_path,
            output_file=out_path,
            background_media=job.background_media,
            duration=job.duration,
            progress_callback=self.progress_reporter.emit,
            job_id=str(job.usfm_file),
            worker_id=worker_id,
            book=job.book,
            chapter=job.chapter,
            watermark=job.watermark,
        )

        job.render_time = time.time() - start_t

        if render_success:
            job.status = "SUCCESS"
            if not job.keep_ass:
                try:
                    ass_path.unlink()
                except Exception:
                    pass
        else:
            job.status = "FAILED"
            job.error_msg = msg
            self.progress_reporter.emit(
                ProgressEvent(
                    job_id=str(job.usfm_file),
                    worker_id=worker_id,
                    status="ERROR",
                    percent=0.0,
                    book=job.book,
                    chapter=job.chapter,
                    message=msg,
                )
            )

        return job

    def _preprocess_background_media(self):
        """
        Automatically preprocesses and caches background video files down to the target
        project resolution before launching parallel rendering workers.
        This eliminates CPU decoding and downscaling overhead during multi-worker execution.
        """
        try:
            video_cfg = self.config.raw_config.get("video", {})
            res_str = video_cfg.get("resolution", "1920x1080")
            if "x" in res_str:
                target_x, target_y = map(int, res_str.split("x"))
            else:
                target_x, target_y = 1920, 1080

            fps = video_cfg.get("fps", 24)
            scaling_mode = video_cfg.get("scaling_mode", "pad").lower()
            if scaling_mode == "crop":
                scale_filter = f"scale={target_x}:{target_y}:force_original_aspect_ratio=increase,crop={target_x}:{target_y}"
            elif scaling_mode == "stretch":
                scale_filter = f"scale={target_x}:{target_y}"
            else:  # default 'pad'
                scale_filter = f"scale={target_x}:{target_y}:force_original_aspect_ratio=decrease,pad={target_x}:{target_y}:(ow-iw)/2:(oh-ih)/2"

            out_dir = Path(
                self.config.raw_config.get("project", {}).get("output_dir", "output")
            )
            cache_dir = out_dir / ".cache"

            # Check unique background videos across all jobs
            unique_bgs = {}
            for job in self.jobs:
                bg = job.background_media or video_cfg.get("background_media")
                if not bg:
                    continue
                bg_path = Path(bg)
                if not bg_path.exists() or not bg_path.is_file():
                    continue
                ext = bg_path.suffix.lower()
                if ext in [
                    ".mp4",
                    ".mov",
                    ".mkv",
                    ".avi",
                    ".webm",
                    ".ts",
                    ".m4v",
                    ".wmv",
                ]:
                    unique_bgs[str(bg_path.resolve())] = bg_path

            for abs_path_str, bg_path in unique_bgs.items():
                # Probe resolution using ffprobe
                probe_cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "csv=s=x:p=0",
                    str(bg_path),
                ]
                res = subprocess.run(
                    probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if res.returncode != 0 or not res.stdout.strip():
                    continue

                parts = res.stdout.strip().split("x")
                if len(parts) != 2:
                    continue
                w, h = int(parts[0]), int(parts[1])

                # 1. Warn if background media is below target resolution (e.g. < 1080p)
                if w < target_x or h < target_y:
                    print(
                        f"\n[!] WARNING: The background video '{bg_path.name}' resolution ({w}x{h}) is lower than your target output resolution ({target_x}x{target_y})."
                    )
                    print(
                        "[!] The background will be upscaled, which may result in lower visual quality or blurriness in the final video!\n"
                    )
                    continue

                # 2. Check if user wants to reduce high-res (e.g. > 1080p) to 1080p
                if (w > 1920 or h > 1080) and (target_x > 1920 or target_y > 1080):
                    if not self.auto_yes and sys.stdin.isatty():
                        print(
                            f"\n[?] Notice: Both background video '{bg_path.name}' ({w}x{h}) and target output ({target_x}x{target_y}) are high resolution."
                        )
                        print(
                            "    Processing 4K/high-res video across multiple parallel workers is CPU/GPU intensive."
                        )
                        try:
                            ans = (
                                input(
                                    "    Would you like to reduce output quality and background to 1080p (1920x1080) for faster batch rendering? [y/N]: "
                                )
                                .strip()
                                .lower()
                            )
                            if ans in ["y", "yes"]:
                                target_x, target_y = 1920, 1080
                                self.config.raw_config["video"][
                                    "resolution"
                                ] = "1920x1080"
                                if scaling_mode == "crop":
                                    scale_filter = f"scale={target_x}:{target_y}:force_original_aspect_ratio=increase,crop={target_x}:{target_y}"
                                elif scaling_mode == "stretch":
                                    scale_filter = f"scale={target_x}:{target_y}"
                                else:
                                    scale_filter = f"scale={target_x}:{target_y}:force_original_aspect_ratio=decrease,pad={target_x}:{target_y}:(ow-iw)/2:(oh-ih)/2"
                        except (EOFError, KeyboardInterrupt):
                            pass

                loop_xfade = float(
                    video_cfg.get("loop_crossfade_sec", 0.0)
                    or video_cfg.get("crossfade_sec", 0.0)
                    or 0.0
                )

                # If resolution already matches target resolution and no loop crossfade requested, no need to downscale
                if w <= target_x and h <= target_y and loop_xfade <= 0:
                    continue

                cache_dir.mkdir(parents=True, exist_ok=True)
                xf_suffix = f"_xf{loop_xfade}s" if loop_xfade > 0 else ""
                cached_filename = f"{bg_path.stem}_scaled_{target_x}x{target_y}_{fps}fps{xf_suffix}{bg_path.suffix}"
                cached_path = cache_dir / cached_filename

                # Check if cached file already exists and is up to date
                if cached_path.exists() and cached_path.stat().st_size > 0:
                    if cached_path.stat().st_mtime >= bg_path.stat().st_mtime:
                        print(
                            f"[*] Using preprocessed {target_x}x{target_y} cached background: {cached_filename}"
                        )
                        for job in self.jobs:
                            job_bg = job.background_media or video_cfg.get(
                                "background_media"
                            )
                            if job_bg and Path(job_bg).resolve() == bg_path.resolve():
                                job.background_media = str(cached_path)
                        continue

                # 3. Prompt user if they want to downscale high-res background to target resolution
                if (
                    not self.auto_yes
                    and sys.stdin.isatty()
                    and (w > target_x or h > target_y)
                ):
                    print(
                        f"\n[?] Notice: Background video '{bg_path.name}' resolution ({w}x{h}) is higher than target project resolution ({target_x}x{target_y})."
                    )
                    try:
                        ans = (
                            input(
                                f"    Would you like to downscale and cache it to {target_x}x{target_y} for significantly faster batch rendering? [Y/n]: "
                            )
                            .strip()
                            .lower()
                        )
                        if ans in ["n", "no"]:
                            print(
                                f"[*] Keeping original high resolution ({w}x{h}) for rendering without caching.\n"
                            )
                            continue
                    except (EOFError, KeyboardInterrupt):
                        continue

                if loop_xfade > 0:
                    print(
                        f"[*] Preprocessing background video: downscaling {bg_path.name} ({w}x{h}) and applying {loop_xfade}s seamless loop crossfade -> {cached_filename}..."
                    )
                else:
                    print(
                        f"[*] Preprocessing background video: downscaling {bg_path.name} ({w}x{h}) -> {cached_filename} ({target_x}x{target_y}) for fast batch rendering..."
                    )

                # Determine fast GPU/CPU encoder for caching
                codec_req = video_cfg.get("codec", "libx264")
                cache_codec = self.builder.detect_best_video_codec(codec_req)

                bg_dur = 0.0
                if loop_xfade > 0:
                    try:
                        dur_res = subprocess.run(
                            [
                                "ffprobe",
                                "-v",
                                "error",
                                "-show_entries",
                                "format=duration",
                                "-of",
                                "default=noprint_wrappers=1:nokey=1",
                                str(bg_path),
                            ],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                        if dur_res.returncode == 0 and dur_res.stdout.strip():
                            bg_dur = float(dur_res.stdout.strip())
                    except Exception:
                        pass

                if loop_xfade > 0 and bg_dur > 2 * loop_xfade:
                    offset = bg_dur - 2 * loop_xfade
                    fc_xfade = f"[0:v]{scale_filter},split=2[vmain][vstart];[vmain]trim=start={loop_xfade},setpts=PTS-STARTPTS[main];[vstart]trim=start=0:end={loop_xfade},setpts=PTS-STARTPTS[start];[main][start]xfade=transition=fade:duration={loop_xfade}:offset={offset:.3f}[outv]"
                    ff_cmd = [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(bg_path),
                        "-filter_complex",
                        fc_xfade,
                        "-map",
                        "[outv]",
                        "-c:v",
                        cache_codec,
                        "-preset",
                        "fast",
                    ]
                else:
                    ff_cmd = [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(bg_path),
                        "-vf",
                        scale_filter,
                        "-c:v",
                        cache_codec,
                        "-preset",
                        "fast",
                    ]
                if "nvenc" in cache_codec:
                    ff_cmd.extend(["-cq", "18"])
                elif "qsv" in cache_codec or "amf" in cache_codec:
                    pass
                else:
                    ff_cmd.extend(["-crf", "18"])
                ff_cmd.extend(["-r", str(fps), "-an", str(cached_path)])

                proc = subprocess.run(
                    ff_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if (
                    proc.returncode == 0
                    and cached_path.exists()
                    and cached_path.stat().st_size > 0
                ):
                    # Update all jobs referencing this background media to use the cached file!
                    for job in self.jobs:
                        job_bg = job.background_media or video_cfg.get(
                            "background_media"
                        )
                        if job_bg and Path(job_bg).resolve() == bg_path.resolve():
                            job.background_media = str(cached_path)
                else:
                    print(
                        f"[!] Warning: Failed to preprocess background video {bg_path.name}. Falling back to original file."
                    )
        except Exception as e:
            print(
                f"[!] Warning: Automatic background preprocessing encountered an issue: {e}. Using original files."
            )

    def run_all(self, max_workers=1):
        """
        Execute all jobs in the queue sequentially or concurrently.
        Returns summary dictionary.
        """
        print(
            f"=== Starting Batch Run ({len(self.jobs)} jobs, {max_workers} workers) ==="
        )
        self._preprocess_background_media()
        start_total = time.time()

        if max_workers > 1 and len(self.jobs) > 1:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                futures = [
                    executor.submit(
                        self._execute_single_job, job, idx % max_workers + 1
                    )
                    for idx, job in enumerate(self.jobs)
                ]
                concurrent.futures.wait(futures)
        else:
            for job in self.jobs:
                self._execute_single_job(job, worker_id=1)

        total_time = time.time() - start_total
        succeeded = sum(1 for j in self.jobs if j.status == "SUCCESS")
        failed = sum(1 for j in self.jobs if j.status == "FAILED")

        self._generate_publishing_manifests()

        return {
            "total_time": total_time,
            "succeeded": succeeded,
            "failed": failed,
            "jobs": self.jobs,
        }

    def print_summary(self, res):
        """
        Print the rich batch summary tables and FINAL RESULTS panel for a run_all() result.

        Deliberately NOT called from inside run_all() itself: a Rich Progress/Live
        display (e.g. TerminalProgressObserver) is typically still active for the
        duration of run_all(), and printing other Console output while it's active
        gets clobbered by the Live display's own redraws (this is why "Total Elapsed"
        never showed up for multi-chapter batches previously - only single-job runs,
        where the timing happened to coincide with the observer already stopping).
        Callers must call observer.stop() first, then this method.
        """
        total_time = res["total_time"]
        succeeded = res["succeeded"]
        failed = res["failed"]

        print("")
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel

            console = Console()

            table = Table(
                title="[bold cyan]📊 Scripture Conversion Batch Summary[/bold cyan]",
                border_style="blue",
                header_style="bold yellow",
                show_lines=True,
            )
            table.add_column("#", justify="center", style="dim", width=4)
            table.add_column("Book", justify="center", style="bold white", width=6)
            table.add_column("Ch", justify="center", style="cyan", width=5)
            table.add_column("Output File", style="green")
            table.add_column("Duration", justify="right", style="yellow", width=10)
            table.add_column("Encoder", justify="center", style="bold cyan", width=14)
            table.add_column("Status", justify="center", width=12)
            table.add_column("Details", style="dim")

            book_stats = {}
            for idx, job in enumerate(self.jobs, 1):
                b = job.book or "UNKNOWN"
                ch_str = (
                    f"{job.chapter:02d}"
                    if isinstance(job.chapter, int)
                    else str(job.chapter or "-")
                )
                if b not in book_stats:
                    book_stats[b] = {
                        "count": 0,
                        "success": 0,
                        "fail": 0,
                        "cpu_time": 0.0,
                        "gpu_time": 0.0,
                        "total_time": 0.0,
                    }
                book_stats[b]["count"] += 1
                book_stats[b]["total_time"] += job.render_time
                if getattr(job, "used_gpu", False):
                    book_stats[b]["gpu_time"] += job.render_time
                else:
                    book_stats[b]["cpu_time"] += job.render_time
                if job.status == "SUCCESS":
                    book_stats[b]["success"] += 1
                    status_badge = "[bold green]✔ SUCCESS[/bold green]"
                    details = "-"
                else:
                    book_stats[b]["fail"] += 1
                    status_badge = "[bold red]✖ FAILED[/bold red]"
                    details = f"[red]{job.error_msg or 'Unknown error'}[/red]"

                dur_str = (
                    f"{int(job.render_time // 60)}m {job.render_time % 60:.1f}s"
                    if job.render_time >= 60
                    else f"{job.render_time:.2f}s"
                )
                enc_badge = (
                    f"[bold green]{getattr(job, 'codec_used', 'unknown')} (GPU)[/bold green]"
                    if getattr(job, "used_gpu", False)
                    else f"[cyan]{getattr(job, 'codec_used', 'libx264')} (CPU)[/cyan]"
                )
                table.add_row(
                    str(idx),
                    b,
                    ch_str,
                    Path(job.output_file).name,
                    dur_str,
                    enc_badge,
                    status_badge,
                    details,
                )

            console.print(table)

            # Print Per-Book Summary Table
            summary_table = Table(
                title="[bold magenta]📈 Per-Book Execution Summary[/bold magenta]",
                border_style="magenta",
                header_style="bold white",
            )
            summary_table.add_column("Book", style="bold yellow")
            summary_table.add_column("Chapters", justify="center")
            summary_table.add_column("Succeeded", justify="center", style="green")
            summary_table.add_column("Failed", justify="center", style="red")
            summary_table.add_column(
                "Total GPU Time", justify="right", style="bold green"
            )
            summary_table.add_column("Total CPU Time", justify="right", style="cyan")
            summary_table.add_column("Avg Time / Ch", justify="right", style="white")

            for b, stats in book_stats.items():
                tot_c = stats["count"]
                avg_t = stats["total_time"] / tot_c if tot_c > 0 else 0
                gpu_str = (
                    f"{int(stats['gpu_time'] // 60)}m {stats['gpu_time'] % 60:.1f}s"
                    if stats["gpu_time"] >= 60
                    else f"{stats['gpu_time']:.2f}s"
                )
                if stats["gpu_time"] == 0:
                    gpu_str = "-"
                cpu_str = (
                    f"{int(stats['cpu_time'] // 60)}m {stats['cpu_time'] % 60:.1f}s"
                    if stats["cpu_time"] >= 60
                    else f"{stats['cpu_time']:.2f}s"
                )
                if stats["cpu_time"] == 0:
                    cpu_str = "-"
                avg_str = f"{avg_t:.2f}s"
                summary_table.add_row(
                    b,
                    str(tot_c),
                    str(stats["success"]),
                    str(stats["fail"]),
                    gpu_str,
                    cpu_str,
                    avg_str,
                )

            console.print(summary_table)

            tot_str = (
                f"{int(total_time // 60)}m {total_time % 60:.1f}s"
                if total_time >= 60
                else f"{total_time:.2f}s"
            )
            total_gpu_time = sum(
                getattr(j, "render_time", 0.0)
                for j in self.jobs
                if getattr(j, "used_gpu", False)
            )
            total_cpu_time = sum(
                getattr(j, "render_time", 0.0)
                for j in self.jobs
                if not getattr(j, "used_gpu", False)
            )

            time_parts = [
                f"[bold white]Total Elapsed:[/] [bold yellow]{tot_str}[/bold yellow]"
            ]
            if total_gpu_time > 0:
                g_str = (
                    f"{int(total_gpu_time // 60)}m {total_gpu_time % 60:.1f}s"
                    if total_gpu_time >= 60
                    else f"{total_gpu_time:.2f}s"
                )
                time_parts.append(
                    f"[bold green]GPU Render Time:[/] [bold green]{g_str}[/bold green]"
                )
            if total_cpu_time > 0:
                c_str = (
                    f"{int(total_cpu_time // 60)}m {total_cpu_time % 60:.1f}s"
                    if total_cpu_time >= 60
                    else f"{total_cpu_time:.2f}s"
                )
                time_parts.append(
                    f"[bold cyan]CPU Render Time:[/] [bold cyan]{c_str}[/bold cyan]"
                )

            time_summary = "  |  ".join(time_parts)
            console.print(
                Panel.fit(
                    f"{time_summary}\n"
                    f"[green]Succeeded:[/] [bold green]{succeeded}[/bold green]  |  "
                    f"[red]Failed:[/] [bold red]{failed}[/bold red]",
                    title="[bold green]🏁 FINAL RESULTS 🏁[/bold green]",
                    border_style="green",
                )
            )
        except Exception:
            print("\n=== Batch Run Complete ===")
            total_gpu_time = sum(
                getattr(j, "render_time", 0.0)
                for j in self.jobs
                if getattr(j, "used_gpu", False)
            )
            total_cpu_time = sum(
                getattr(j, "render_time", 0.0)
                for j in self.jobs
                if not getattr(j, "used_gpu", False)
            )
            print(
                f"Total time: {total_time:.2f}s | GPU Time: {total_gpu_time:.2f}s | CPU Time: {total_cpu_time:.2f}s | Succeeded: {succeeded} | Failed: {failed}"
            )
            for idx, job in enumerate(self.jobs, 1):
                status_symbol = "[OK]" if job.status == "SUCCESS" else "[FAIL]"
                enc_str = f"[{getattr(job, 'codec_used', 'unknown')}]"
                print(
                    f"[{idx}] {status_symbol} {Path(job.output_file).name} {enc_str} ({job.render_time:.2f}s)"
                )
                if job.error_msg:
                    print(f"    Error: {job.error_msg}")

    def _generate_publishing_manifests(self):
        """Generate outbox manifest and offline packages for successfully rendered jobs."""
        if not self.config:
            return
        pub_cfg = self.config.publishing
        if not pub_cfg.get("enabled", False) and not pub_cfg.get(
            "generate_offline_package", True
        ):
            return

        out_dir = Path(self.config.project.get("output_dir", "output"))
        manifest_file = out_dir / "publish_manifest.json"
        mgr = ManifestManager(manifest_file)

        lang = self.config.project.get("language", "Language")
        t_copy = self.config.project.get("text_copyright", "")
        a_copy = self.config.project.get("audio_copyright", "")

        added_count = 0
        for job in self.jobs:
            if job.status != "SUCCESS" or not job.output_file:
                continue

            book = job.book or "Scripture"
            ch = job.chapter if isinstance(job.chapter, int) else 1
            entry_id = f"{book}_Ch{ch:02d}"

            title = resolve_metadata_template(
                pub_cfg.get("title_template", ""),
                book=book,
                chapter=ch,
                language=lang,
                text_copyright=t_copy,
                audio_copyright=a_copy,
            )
            desc = resolve_metadata_template(
                pub_cfg.get("description_template", ""),
                book=book,
                chapter=ch,
                language=lang,
                text_copyright=t_copy,
                audio_copyright=a_copy,
            )
            tags = [
                resolve_metadata_template(t, book=book, chapter=ch, language=lang)
                for t in pub_cfg.get("tags", [])
            ]

            thumb_path = None
            possible_thumbs = [
                Path(job.output_file).with_name("title_card.jpg"),
                out_dir / "title_card.jpg",
            ]
            for pt in possible_thumbs:
                if pt.exists():
                    thumb_path = str(pt)
                    break

            entry = ManifestEntry(
                id=entry_id,
                video_path=str(job.output_file),
                thumbnail_path=thumb_path,
                book=book,
                chapter=ch,
                language=lang,
                title=title,
                description=desc,
                privacy_status=pub_cfg.get("privacy_status", "unlisted"),
                category_id=str(pub_cfg.get("category_id", "22")),
                playlist_name=pub_cfg.get("playlist_name", ""),
                tags=tags,
            )
            mgr.add_or_update(entry)
            added_count += 1

            if pub_cfg.get("generate_offline_package", True):
                try:
                    generate_offline_package(entry, out_dir)
                except Exception as e:
                    print(
                        f"[!] Warning: Could not generate offline package for {entry_id}: {e}"
                    )

        if added_count > 0:
            mgr.save()
            print(
                f"\n[+] YouTube Outbox Manifest updated: {manifest_file} ({added_count} items)"
            )
