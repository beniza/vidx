"""
Command Line Interface (CLI) for VIDX
Provides command-line options for running single video conversions or batch jobs from YAML configs.
"""

import re
import sys
import argparse
from pathlib import Path
from typing import Optional

from .config import Config
from .batch_runner import BatchRunner
from .progress import TerminalProgressObserver
from .manifest import ManifestManager
from .youtube import YouTubePublisher, QuotaExceededError, YOUTUBE_AVAILABLE, _YOUTUBE_IMPORT_ERROR
from . import __version__


def run_publisher(manifest_path: str, config: Optional[Config] = None):
    """Execute outbox publishing loop against YouTube Data API."""
    if not YOUTUBE_AVAILABLE:
        print(
            f"[-] Error: YouTube API dependencies failed to load: {_YOUTUBE_IMPORT_ERROR}"
        )
        print("Run: pip install vidx[youtube] (or use standard offline studio upload packages)")
        sys.exit(1)

    p = Path(manifest_path)
    if not p.exists():
        print(f"[-] Error: Publishing manifest not found at: {p.resolve()}")
        sys.exit(1)

    mgr = ManifestManager(p)
    pending = mgr.get_pending_entries()
    if not pending:
        print("[+] No pending items to publish in manifest.")
        return

    secrets_file = "~/.vidx/client_secrets.json"
    if config and config.publishing.get("client_secrets_file"):
        secrets_file = config.publishing.get("client_secrets_file")

    # Default token cache lives alongside the manifest so each project/channel
    # keeps its own YouTube login instead of sharing the global ~/.vidx token.
    token_file = str(p.parent / "youtube_token.json")
    if config and config.publishing.get("token_file"):
        token_file = config.publishing.get("token_file")

    print(f"[*] YouTube token cache: {Path(token_file).expanduser().resolve()}")
    try:
        pub = YouTubePublisher(client_secrets_file=secrets_file, token_file=token_file)
    except Exception as e:
        print(f"[-] YouTube Publisher Init Error: {e}")
        sys.exit(1)

    print(f"\n=== Starting YouTube Publishing Loop ({len(pending)} pending items) ===")
    for idx, entry in enumerate(pending, 1):
        print(f"\n[{idx}/{len(pending)}] ▶ Publishing: {entry.title}")
        try:
            video_id = pub.publish_entry(
                entry,
                progress_callback=lambda prog: print(
                    f"    Upload progress: {int(prog * 100)}%", end="\r"
                ),
            )
            print(f"    ✔ Uploaded successfully! YouTube ID: {video_id}          ")
            mgr.update_status(entry.id, "UPLOADED", youtube_video_id=video_id)
        except QuotaExceededError as qe:
            print(f"\n[!] ⚠ {qe}")
            break
        except Exception as e:
            print(f"\n[-] ✖ Upload failed: {e}")
            mgr.update_status(entry.id, "FAILED", error_message=str(e))


def run_align(args):
    """Generate a SAB-style timing file from audio + USFM via forced alignment."""
    from .align import (
        ALIGN_AVAILABLE, _ALIGN_IMPORT_ERROR, align_segments, audio_duration,
        segments_from_usfm, to_audacity_labels, from_audacity_labels,
        write_timing_file, DEFAULT_SEPARATORS,
    )
    from .usfm_parser import USFMParser, TimingParser

    # Audacity round-trip: the timing body is already a label track, so the only
    # work is stripping and restoring the USFM-ish header.
    if args.to_labels:
        tp = TimingParser(Path(args.timing).read_text(encoding="utf-8-sig"),
                          filepath=args.timing)
        rows = [(e["start"], e["end"], e["segment"]) for e in tp.entries]
        Path(args.to_labels).write_text(to_audacity_labels(rows), encoding="utf-8")
        print(f"[+] Wrote Audacity label track: {args.to_labels}")
        print("    Audacity: File > Import > Labels, drag boundaries, then Export Labels.")
        return
    if args.from_labels:
        src = Path(args.timing)
        tp = TimingParser(src.read_text(encoding="utf-8-sig"), filepath=src)
        rows = from_audacity_labels(Path(args.from_labels).read_text(encoding="utf-8"))
        out = args.output or str(src)
        write_timing_file(out, rows, book=args.book or "", chapter=tp.chapter or "",
                          level=tp.level or "verse", separators=tp.separators)
        print(f"[+] Merged {len(rows)} edited labels back into: {out}")
        return

    if not ALIGN_AVAILABLE:
        print(f"[-] Alignment dependencies missing: {_ALIGN_IMPORT_ERROR}")
        print("    Run: pip install vidx[align]")
        sys.exit(1)
    if not (args.usfm and args.audio):
        print("[-] --align requires --usfm and --audio.")
        sys.exit(1)

    usfm_path, audio_path = Path(args.usfm), Path(args.audio)
    for p in (usfm_path, audio_path):
        if not p.exists():
            print(f"[-] Not found: {p}")
            sys.exit(1)

    chapter = args.chapter
    if not chapter:
        m = re.search(r"(\d{1,3})", audio_path.stem)
        chapter = str(int(m.group(1))) if m else None
    if not chapter:
        print("[-] Could not infer chapter number; pass --chapter.")
        sys.exit(1)

    up = USFMParser(usfm_path.read_text(encoding="utf-8-sig"), target_chapter=str(chapter))
    segments = segments_from_usfm(up, level=args.level, separators=DEFAULT_SEPARATORS,
                                  headings=not args.no_headings)
    if not segments:
        print(f"[-] No verses found for chapter {chapter} in {usfm_path.name}.")
        sys.exit(1)

    dur = audio_duration(audio_path)
    print(f"[*] Aligning {usfm_path.name} ch.{chapter} against {audio_path.name}")
    print(f"    {len(segments)} {args.level} segments | {dur / 60:.1f} min audio | lang={args.lang or 'auto'}")

    def progress(done, total):
        print(f"    frames {done}/{total} chunks", end="\r")

    rows = align_segments(audio_path, segments, lang=args.lang, progress=progress)
    print(" " * 40, end="\r")

    m_id = re.search(r"\\id\s+(\w+)", up.content or "")
    book = args.book or (m_id.group(1) if m_id else "")

    # Timing files are project *inputs*, so they belong beside the audio they
    # describe -- not in output/. Teams keep audio in <x>/audio/ and timings in
    # <x>/timing/ (both SAB layouts in this repo do), so honour that when we see
    # it and otherwise just sit next to the audio file.
    filename = f"{book or 'CH'}-{int(chapter):02d}-timing.txt"
    if args.output:
        out_path = Path(args.output)
        if out_path.is_dir() or not out_path.suffix:
            out_path.mkdir(parents=True, exist_ok=True)
            out_path = out_path / filename
    elif audio_path.parent.name.lower() == "audio":
        timing_dir = audio_path.parent.parent / "timing"
        timing_dir.mkdir(parents=True, exist_ok=True)
        out_path = timing_dir / filename
    else:
        out_path = audio_path.with_name(filename)

    if out_path.exists() and not args.yes:
        try:
            reply = input(f"[?] {out_path} exists. Overwrite? [y/N] ").strip().lower()
        except EOFError:  # non-interactive run: never clobber hand-tuned timings
            reply = "n"
        if reply not in ("y", "yes"):
            print("[-] Aborted; existing timing file left untouched. Use -y to overwrite.")
            sys.exit(1)

    out = str(out_path)
    write_timing_file(out, rows, book=book, chapter=chapter, level=args.level,
                      separators=DEFAULT_SEPARATORS)
    print(f"[+] Wrote {len(rows)} timings: {out}")
    print(f"    Fine-tune: vidx --align --timing {out} --to-labels labels.txt")


def main():
    parser = argparse.ArgumentParser(
        description="VIDX: Scripture Video Generator (combines USFM text, audio, and timing into video)."
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"VIDX {__version__}"
    )
    parser.add_argument(
        "-c", "--config", type=str, help="Path to YAML configuration file."
    )
    parser.add_argument("--usfm", type=str, help="Path to USFM scripture file.")
    parser.add_argument("--timing", type=str, help="Path to timing file (.txt).")
    parser.add_argument(
        "--audio", type=str, help="Path to audio file (.mp3, .wav, .mpeg)."
    )
    parser.add_argument(
        "-o", "--output", type=str, help="Path for output video file (.mp4)."
    )
    parser.add_argument(
        "-b", "--bg", type=str, help="Path to background media (.mp4, .jpg, .png)."
    )
    parser.add_argument(
        "-t",
        "--duration",
        type=float,
        help="Optional duration limit in seconds (for quick testing).",
    )
    parser.add_argument(
        "--keep-ass",
        action="store_true",
        default=True,
        help="Keep intermediate .ass subtitle file.",
    )
    parser.add_argument(
        "--clean-ass",
        action="store_true",
        help="Delete intermediate .ass subtitle file after successful render.",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=1,
        help="Number of parallel rendering workers.",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only generate subtitle files without rendering video.",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["ass", "srt", "both"],
        help="Subtitle format to generate (ass, srt, both).",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Enable automatic GPU hardware acceleration for video encoding.",
    )
    parser.add_argument(
        "--codec",
        type=str,
        help="Specify video codec explicitly (e.g. 'auto', 'h264_nvenc', 'libx264').",
    )
    parser.add_argument(
        "--res",
        "--resolution",
        dest="resolution",
        type=str,
        help="Override output resolution (e.g. 1920x1080, 3840x2160, 1080x1920).",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Automatically answer yes to prompts (e.g. downscale high-res background to 1080p).",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish rendered videos to YouTube using the outbox manifest.",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        help="Path to publish_manifest.json to publish without re-rendering.",
    )

    align_grp = parser.add_argument_group("timing generation (forced alignment)")
    align_grp.add_argument(
        "--align",
        action="store_true",
        help="Generate a timing file from --usfm + --audio instead of rendering.",
    )
    align_grp.add_argument(
        "--lang",
        type=str,
        help="ISO-639-3 code for romanization (e.g. mal, snd, hin). Improves accuracy.",
    )
    align_grp.add_argument(
        "--level",
        type=str,
        choices=["verse", "phrase"],
        default="verse",
        help="Timing granularity to generate (default: verse).",
    )
    align_grp.add_argument(
        "--chapter", type=str, help="Chapter number (inferred from audio filename if omitted)."
    )
    align_grp.add_argument("--book", type=str, help="Book code for the \\id header (e.g. MRK).")
    align_grp.add_argument(
        "--no-headings",
        action="store_true",
        help="Skip \\s section headings (use when the narrator does not read them aloud).",
    )
    align_grp.add_argument(
        "--to-labels", type=str, metavar="FILE",
        help="Export --timing as an Audacity label track for waveform fine-tuning.",
    )
    align_grp.add_argument(
        "--from-labels", type=str, metavar="FILE",
        help="Merge an edited Audacity label track back into --timing.",
    )

    args = parser.parse_args()

    if args.align or args.to_labels or args.from_labels:
        run_align(args)
        sys.exit(0)

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

    if args.gpu or args.codec or args.resolution:
        if "video" not in config.raw_config:
            config.raw_config["video"] = {}
        if args.codec or args.gpu:
            config.raw_config["video"]["codec"] = (
                args.codec if args.codec else ("auto" if args.gpu else "libx264")
            )
        if args.resolution:
            config.raw_config["video"]["resolution"] = args.resolution

    keep_ass = not args.clean_ass if args.clean_ass else args.keep_ass

    # Mode 0: Standalone publish from manifest or default publish
    if args.manifest or (args.publish and not args.config and not args.usfm):
        man_path = args.manifest or (
            "output/publish_manifest.json"
            if Path("output/publish_manifest.json").exists()
            else "publish_manifest.json"
        )
        run_publisher(man_path, config=config if args.config else None)
        sys.exit(0)

    # Mode 1: Single Job from CLI arguments
    elif args.usfm and args.timing and (args.audio or args.generate_only):
        out_f = args.output or (
            str(Path(args.audio).with_suffix(".mp4"))
            if args.audio
            else str(Path(args.usfm).with_suffix(".mp4"))
        )
        audio_f = args.audio or str(Path(args.usfm).with_suffix(".mp3"))
        runner = BatchRunner(config=config, auto_yes=args.yes)
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
            keep_ass=keep_ass,
        )
        observer = TerminalProgressObserver(total_jobs=len(runner.jobs), use_rich=True)
        runner.progress_reporter.subscribe(observer.on_progress)
        observer.start()
        try:
            res = runner.run_all(max_workers=1)
        finally:
            observer.stop()
        runner.print_summary(res)
        if args.publish and res["failed"] == 0:
            out_dir = Path(config.project.get("output_dir", "."))
            run_publisher(str(out_dir / "publish_manifest.json"), config=config)
        sys.exit(0 if res["failed"] == 0 else 1)

    # Mode 2: Batch Job from YAML configuration
    elif args.config:
        runner = BatchRunner(config=config, auto_yes=args.yes)
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
        observer = TerminalProgressObserver(total_jobs=len(runner.jobs), use_rich=True)
        runner.progress_reporter.subscribe(observer.on_progress)
        observer.start()
        try:
            res = runner.run_all(max_workers=args.workers)
        finally:
            observer.stop()
        runner.print_summary(res)
        if args.publish and res["failed"] == 0:
            out_dir = Path(config.project.get("output_dir", "output"))
            run_publisher(str(out_dir / "publish_manifest.json"), config=config)
        sys.exit(0 if res["failed"] == 0 else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
