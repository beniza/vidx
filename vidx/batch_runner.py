"""
Batch Runner Module for VIDX
Orchestrates multi-chapter conversion and video rendering jobs with progress logging
and intermediate file management.
"""
import time
import concurrent.futures
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

from .ass_generator import convert_to_ass
from .ffmpeg_builder import FFmpegBuilder
from .config import Config
from .progress import ProgressReporter, ProgressEvent


@dataclass
class Job:
    usfm_file: str
    timing_file: str
    audio_file: str
    output_file: str
    background_media: Optional[str] = None
    duration: Optional[float] = None
    keep_ass: bool = True
    status: str = "PENDING"
    error_msg: str = ""
    render_time: float = 0.0
    book: Optional[str] = None
    chapter: Optional[int] = None


class BatchRunner:
    """Manages execution of multiple video rendering jobs."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.jobs: List[Job] = []
        self.builder = FFmpegBuilder(self.config.raw_config)
        self.progress_reporter = ProgressReporter()
        
    def add_job(self, usfm_file, timing_file, audio_file, output_file, background_media=None, duration=None, keep_ass=True):
        """Add a rendering job to the batch queue."""
        job = Job(
            usfm_file=str(usfm_file),
            timing_file=str(timing_file),
            audio_file=str(audio_file),
            output_file=str(output_file),
            background_media=str(background_media) if background_media else None,
            duration=duration,
            keep_ass=keep_ass
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
                
            bg_media = item.get("background", default_bg)
            dur = item.get("duration", None)
            keep = item.get("keep_ass", True)
            
            self.add_job(usfm_f, timing_f, audio_f, out_f, bg_media, dur, keep)
            
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
                if usfm_path.exists():
                    with open(usfm_path, "r", encoding="utf-8", errors="ignore") as f:
                        for _ in range(20):
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
                
        self.progress_reporter.emit(ProgressEvent(
            job_id=str(job.usfm_file), worker_id=worker_id, status="STARTING",
            percent=0.0, book=job.book, chapter=job.chapter, message="Starting job..."
        ))
        
        # Determine subtitle format and generate-only mode
        sub_format = getattr(self, 'subtitle_format', None) or self.config.project.get("subtitle_format", "ass")
        sub_format = str(sub_format).lower().strip()
        gen_only = getattr(self, 'generate_only', False) or self.config.project.get("generate_only", False) or self.config.project.get("subtitle_only", False)
        
        # Verify inputs exist
        if not usfm_path.exists():
            job.status = "FAILED"
            job.error_msg = f"USFM file not found: {usfm_path}"
            self.progress_reporter.emit(ProgressEvent(
                job_id=str(job.usfm_file), worker_id=worker_id, status="ERROR",
                percent=0.0, book=job.book, chapter=job.chapter, message=job.error_msg
            ))
            return job
        if not timing_path.exists():
            job.status = "FAILED"
            job.error_msg = f"Timing file not found: {timing_path}"
            self.progress_reporter.emit(ProgressEvent(
                job_id=str(job.usfm_file), worker_id=worker_id, status="ERROR",
                percent=0.0, book=job.book, chapter=job.chapter, message=job.error_msg
            ))
            return job
        if not gen_only and not audio_path.exists():
            job.status = "FAILED"
            job.error_msg = f"Audio file not found: {audio_path}"
            self.progress_reporter.emit(ProgressEvent(
                job_id=str(job.usfm_file), worker_id=worker_id, status="ERROR",
                percent=0.0, book=job.book, chapter=job.chapter, message=job.error_msg
            ))
            return job
            
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ass_path = out_path.with_suffix(".ass")
        
        self.progress_reporter.emit(ProgressEvent(
            job_id=str(job.usfm_file), worker_id=worker_id, status="EXTRACTING_SUBTITLES",
            percent=10.0, book=job.book, chapter=job.chapter, message="Generating subtitles..."
        ))
        
        # 1a. Generate SRT subtitles if requested
        if sub_format in ["srt", "both"]:
            srt_path = out_path.with_suffix(".srt")
            print(f"[*] Generating SRT subtitles: {srt_path.name}")
            from .usfm_parser import convert_to_srt
            srt_success = convert_to_srt(
                usfm_file=usfm_path,
                timing_file=timing_path,
                output_file=srt_path
            )
            if not srt_success or not srt_path.exists():
                job.status = "FAILED"
                job.error_msg = f"SRT generation failed for {srt_path}"
                self.progress_reporter.emit(ProgressEvent(
                    job_id=str(job.usfm_file), worker_id=worker_id, status="ERROR",
                    percent=0.0, book=job.book, chapter=job.chapter, message=job.error_msg
                ))
                return job

        # 1b. Generate ASS subtitles (required if rendering video, or if requested)
        if sub_format in ["ass", "both"] or not gen_only:
            print(f"[*] Generating ASS subtitles: {ass_path.name}")
            success = convert_to_ass(
                usfm_file=usfm_path,
                timing_file=timing_path,
                output_file=ass_path,
                config=self.config.raw_config
            )
            if not success or not ass_path.exists():
                job.status = "FAILED"
                job.error_msg = f"Subtitle generation failed for {ass_path}"
                self.progress_reporter.emit(ProgressEvent(
                    job_id=str(job.usfm_file), worker_id=worker_id, status="ERROR",
                    percent=0.0, book=job.book, chapter=job.chapter, message=job.error_msg
                ))
                return job
                
        if gen_only:
            job.render_time = time.time() - start_t
            job.status = "SUCCESS"
            self.progress_reporter.emit(ProgressEvent(
                job_id=str(job.usfm_file), worker_id=worker_id, status="COMPLETED",
                percent=100.0, book=job.book, chapter=job.chapter, message="Subtitles generated successfully."
            ))
            return job
            
        # 2. Render video using FFmpeg
        print(f"[*] Rendering video: {out_path.name}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        render_success, msg = self.builder.render(
            audio_file=audio_path,
            subtitle_file=ass_path,
            output_file=out_path,
            background_media=job.background_media,
            duration=job.duration,
            progress_callback=self.progress_reporter.emit,
            job_id=str(job.usfm_file),
            worker_id=worker_id,
            book=job.book,
            chapter=job.chapter
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
            self.progress_reporter.emit(ProgressEvent(
                job_id=str(job.usfm_file), worker_id=worker_id, status="ERROR",
                percent=0.0, book=job.book, chapter=job.chapter, message=msg
            ))
            
        return job

    def run_all(self, max_workers=1):
        """
        Execute all jobs in the queue sequentially or concurrently.
        Returns summary dictionary.
        """
        print(f"=== Starting Batch Run ({len(self.jobs)} jobs, {max_workers} workers) ===")
        start_total = time.time()
        
        if max_workers > 1 and len(self.jobs) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(self._execute_single_job, job, idx % max_workers + 1) for idx, job in enumerate(self.jobs)]
                concurrent.futures.wait(futures)
        else:
            for job in self.jobs:
                self._execute_single_job(job, worker_id=1)
                
        total_time = time.time() - start_total
        succeeded = sum(1 for j in self.jobs if j.status == "SUCCESS")
        failed = sum(1 for j in self.jobs if j.status == "FAILED")
        
        print("\n=== Batch Run Complete ===")
        print(f"Total time: {total_time:.2f}s | Succeeded: {succeeded} | Failed: {failed}")
        
        for idx, job in enumerate(self.jobs, 1):
            status_symbol = "[OK]" if job.status == "SUCCESS" else "[FAIL]"
            print(f"[{idx}] {status_symbol} {Path(job.output_file).name} ({job.render_time:.2f}s)")
            if job.error_msg:
                print(f"    Error: {job.error_msg}")
                
        return {
            "total_time": total_time,
            "succeeded": succeeded,
            "failed": failed,
            "jobs": self.jobs
        }
