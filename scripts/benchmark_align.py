"""Align a whole book chapter by chapter, then score it against reference timings.

Exists because "is the aligner still accurate?" was previously answered by hand,
one chapter at a time. Run this after touching anything in vidx/align.py.

    python scripts/benchmark_align.py

Defaults point at the Malayalam Mark corpus in this repo. Override for others:

    python scripts/benchmark_align.py --usfm src/snd/58PHMSND.SFM \
        --audio-dir src/snd/phm/audio --ref-dir src/snd/phm/timing --lang snd
"""

import argparse
import statistics
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn,
)
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vidx.align import (  # noqa: E402
    DEFAULT_SEPARATORS, align_segments, audio_duration, from_audacity_labels,
    segments_from_usfm, write_timing_file,
)
from vidx.usfm_parser import USFMParser  # noqa: E402

console = Console()


def pct(sorted_vals, q):
    """Nearest-rank percentile. Stdlib-only; the sample sizes here are tiny."""
    if not sorted_vals:
        return float("nan")
    i = min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def find_ref(ref_dir, book, chapter):
    """SAB names files like C01-41-MRK-01-timing.txt; match on book+chapter."""
    hits = sorted(Path(ref_dir).glob(f"*{book}-{chapter:02d}-timing.txt"))
    # Skip files VIDX itself wrote (no C##-##- prefix) so we score against SAB only.
    hits = [h for h in hits if not h.name.startswith(f"{book}-")]
    return hits[0] if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usfm", default="src/mal/42MRKMAL10RO.SFM")
    ap.add_argument("--audio-dir", default="src/mal/mrk/audio")
    ap.add_argument("--ref-dir", default="src/mal/mrk/timing")
    ap.add_argument("--out-dir", default="output/align_benchmark")
    ap.add_argument("--book", default="MRK")
    ap.add_argument("--lang", default="mal")
    ap.add_argument("--chapters", default="1-16", help="e.g. 1-16 or 1,5,9")
    ap.add_argument("--level", default="verse", choices=["verse", "phrase"])
    ap.add_argument("--compare-only", metavar="DIR", nargs="?", const="",
                    help="Skip alignment and score timing files that already exist. "
                         "Defaults to --ref-dir, where VIDX writes BOOK-NN-timing.txt "
                         "alongside SAB's C##-##-BOOK-NN-timing.txt.")
    args = ap.parse_args()

    if "-" in args.chapters:
        lo, hi = args.chapters.split("-")
        chapters = list(range(int(lo), int(hi) + 1))
    else:
        chapters = [int(c) for c in args.chapters.split(",")]

    out_dir = Path(args.out_dir)
    results = []

    if args.compare_only is not None:
        # Score timing files that are already on disk. No model, no audio, no ffmpeg.
        src = Path(args.compare_only or args.ref_dir)
        for ch in chapters:
            f = src / f"{args.book}-{ch:02d}-timing.txt"
            if not f.exists():
                console.print(f"[yellow]skip ch {ch}: no {f.name}")
                continue
            rows = from_audacity_labels(f.read_text(encoding="utf-8-sig"))
            results.append({"ch": ch, "rows": rows, "dur": None, "sec": None})
        if not results:
            console.print(f"[red]no {args.book}-NN-timing.txt files found in {src}")
            return 1
        console.print(f"[dim]Scoring {len(results)} existing timing files from {src}[/dim]\n")
        return report(args, results)

    usfm_text = Path(args.usfm).read_text(encoding="utf-8-sig")
    out_dir.mkdir(parents=True, exist_ok=True)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        book_task = prog.add_task(f"[cyan]{args.book} {args.lang}", total=len(chapters))
        for ch in chapters:
            audio = Path(args.audio_dir) / f"{ch:02d}.mp3"
            if not audio.exists():
                console.print(f"[yellow]skip ch {ch}: no {audio}")
                prog.advance(book_task)
                continue

            parser = USFMParser(usfm_text, target_chapter=str(ch))
            segments = segments_from_usfm(parser, level=args.level)
            dur = audio_duration(audio)

            sub = prog.add_task(f"  ch {ch:02d} frames", total=None)
            t0 = time.perf_counter()
            rows = align_segments(
                audio, segments, lang=args.lang,
                progress=lambda i, n, _t=sub: prog.update(_t, completed=i, total=n),
            )
            elapsed = time.perf_counter() - t0
            prog.remove_task(sub)

            out = out_dir / f"{args.book}-{ch:02d}-timing.txt"
            write_timing_file(out, rows, args.book, ch, level=args.level,
                              separators=DEFAULT_SEPARATORS)
            results.append({"ch": ch, "rows": rows, "dur": dur, "sec": elapsed})
            prog.advance(book_task)

    return report(args, results)


def report(args, results):
    """Print the speed and accuracy tables. Speed is skipped in compare-only mode."""
    if not results:
        console.print("[red]nothing aligned")
        return 1

    # ---------------- speed ----------------
    if all(r["sec"] for r in results):
        t = Table(title="Alignment speed", title_style="bold cyan")
        for c, j in [("Ch", "right"), ("Segments", "right"), ("Audio", "right"),
                     ("Align time", "right"), ("Speed", "right")]:
            t.add_column(c, justify=j)
        for r in results:
            t.add_row(f"{r['ch']:02d}", str(len(r["rows"])), f"{r['dur']:.0f}s",
                      f"{r['sec']:.1f}s", f"{r['dur'] / r['sec']:.1f}x")
        tot_a = sum(r["dur"] for r in results)
        tot_s = sum(r["sec"] for r in results)
        t.add_section()
        t.add_row("[bold]All", f"[bold]{sum(len(r['rows']) for r in results)}",
                  f"[bold]{tot_a / 60:.1f}m", f"[bold]{tot_s / 60:.1f}m",
                  f"[bold]{tot_a / tot_s:.1f}x")
        console.print(t)

    # ---------------- accuracy vs reference ----------------
    a = Table(title="Verse-start error vs SAB reference", title_style="bold cyan")
    for c in ["Ch", "Matched", "Median", "p90", "Max", "<=0.5s"]:
        a.add_column(c, justify="right")

    all_err, v1_err, end_err, unmatched = [], [], [], 0
    for r in results:
        ref_path = find_ref(args.ref_dir, args.book, r["ch"])
        if not ref_path:
            a.add_row(f"{r['ch']:02d}", "[yellow]no ref", "-", "-", "-", "-")
            continue
        ref = {sid: (s, e) for s, e, sid in
               from_audacity_labels(ref_path.read_text(encoding="utf-8-sig"))}
        mine = {sid: (s, e) for s, e, sid in r["rows"]}

        errs = []
        for sid, (s, _) in mine.items():
            if sid not in ref:            # headings: VIDX times them, SAB doesn't
                if not sid.startswith("s"):
                    unmatched += 1
                continue
            d = abs(s - ref[sid][0])
            if sid == "1":       # kept out of both tables, reported on its own
                v1_err.append(d)
                continue
            errs.append(d)
            all_err.append(d)

        # Final end is compared separately: SAB pads the last verse over closing
        # audio, VIDX stops at the last spoken character, so mixing it in would
        # just add a known constant offset to the stats.
        last = max(ref, key=lambda k: ref[k][1])
        if last in mine:
            end_err.append((r["ch"], mine[last][1] - ref[last][1]))

        errs.sort()
        a.add_row(f"{r['ch']:02d}", str(len(errs)), f"{statistics.median(errs):.2f}s",
                  f"{pct(errs, 0.90):.2f}s", f"{max(errs):.2f}s",
                  f"{100 * sum(e <= 0.5 for e in errs) / len(errs):.0f}%")

    pool = sorted(all_err)
    if pool:
        a.add_section()
        a.add_row("[bold]All", f"[bold]{len(pool)}",
                  f"[bold]{statistics.median(pool):.2f}s",
                  f"[bold]{pct(pool, 0.90):.2f}s", f"[bold]{max(pool):.2f}s",
                  f"[bold]{100 * sum(e <= 0.5 for e in pool) / len(pool):.0f}%")
    console.print(a)
    console.print("[dim]Verse 1 excluded above; reported separately (chapter "
                  "announcements shift it).[/dim]")

    if v1_err:
        v1 = sorted(v1_err)
        console.print(f"\n[bold]Verse 1[/bold]  n={len(v1)}  "
                      f"median {statistics.median(v1):.2f}s  max {max(v1):.2f}s")
    if end_err:
        d = sorted(x for _, x in end_err)
        worst = min(end_err, key=lambda p: p[1])
        console.print(f"[bold]Last-verse end[/bold]  median {statistics.median(d):+.1f}s, "
                      f"range {d[0]:+.1f}s..{d[-1]:+.1f}s (most negative: ch "
                      f"{worst[0]:02d}). Negative = VIDX stops at the last spoken "
                      f"word where SAB holds the verse over closing audio; this "
                      f"differs per chapter and is expected.")
    if unmatched:
        console.print(f"[yellow]{unmatched} verse ids had no reference match")
    if all(r["sec"] for r in results):
        console.print(f"\nTimings written to [cyan]{args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
