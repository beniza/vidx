"""
Command Line Interface (CLI) for VIDX
Provides command-line options for running single video conversions or batch jobs from YAML configs.
"""
import sys
import argparse
from pathlib import Path

from .config import Config
from .batch_runner import BatchRunner
from .ass_generator import convert_to_ass


def main():
    parser = argparse.ArgumentParser(
        description="VIDX: Scripture Video Generator companion to AUDX (combines USFM text, audio, and timing into video)."
    )
    parser.add_argument("-c", "--config", type=str, help="Path to YAML configuration file.")
    parser.add_argument("--usfm", type=str, help="Path to USFM scripture file.")
    parser.add_argument("--timing", type=str, help="Path to timing file (.txt).")
    parser.add_argument("--audio", type=str, help="Path to audio file (.mp3, .wav, .mpeg).")
    parser.add_argument("-o", "--output", type=str, help="Path for output video file (.mp4).")
    parser.add_argument("-b", "--bg", type=str, help="Path to background media (.mp4, .jpg, .png).")
    parser.add_argument("-t", "--duration", type=float, help="Optional duration limit in seconds (for quick testing).")
    parser.add_argument("--keep-ass", action="store_true", default=True, help="Keep intermediate .ass subtitle file.")
    parser.add_argument("--clean-ass", action="store_true", help="Delete intermediate .ass subtitle file after successful render.")
    parser.add_argument("-w", "--workers", type=int, default=1, help="Number of parallel rendering workers.")
    parser.add_argument("--generate-only", action="store_true", help="Only generate subtitle files without rendering video.")
    parser.add_argument("--format", type=str, choices=["ass", "srt", "both"], help="Subtitle format to generate (ass, srt, both).")
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = Config(config_path=args.config)
    except FileNotFoundError as e:
        print(f"[-] Error: {e}")
        sys.exit(1)
    
    # Override background if specified in CLI
    if args.bg:
        if "video" not in config.raw_config:
            config.raw_config["video"] = {}
        config.raw_config["video"]["background_media"] = args.bg
        
    keep_ass = not args.clean_ass if args.clean_ass else args.keep_ass
    
    # Mode 1: Single Job from CLI arguments
    if args.usfm and args.timing and (args.audio or args.generate_only):
        out_f = args.output or (str(Path(args.audio).with_suffix(".mp4")) if args.audio else str(Path(args.usfm).with_suffix(".mp4")))
        audio_f = args.audio or str(Path(args.usfm).with_suffix(".mp3"))
        runner = BatchRunner(config=config)
        if args.generate_only:
            runner.generate_only = True
        if args.format:
            runner.subtitle_format = args.format
        runner.add_job(
            usfm_file=args.usfm,
            timing_file=args.timing,
            audio_file=audio_f,
            output_file=out_f,
            background_media=args.bg,
            duration=args.duration,
            keep_ass=keep_ass
        )
        res = runner.run_all(max_workers=1)
        sys.exit(0 if res["failed"] == 0 else 1)
            
    # Mode 2: Batch Job from YAML configuration
    elif args.config:
        runner = BatchRunner(config=config)
        if args.generate_only:
            runner.generate_only = True
        if args.format:
            runner.subtitle_format = args.format
        runner.load_jobs_from_config()
        if not runner.jobs:
            print("[-] No jobs defined in YAML configuration under 'jobs' list.")
            sys.exit(1)
        if args.duration is not None:
            for job in runner.jobs:
                job.duration = args.duration
        res = runner.run_all(max_workers=args.workers)
        sys.exit(0 if res["failed"] == 0 else 1)
        
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
