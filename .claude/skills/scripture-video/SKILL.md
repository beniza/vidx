---
name: scripture-video
description: Use when a new VIDX project folder is ready and you need to take it from raw SAB assets to a rendered Scripture video - generating timing files with `vidx --align`, scoring them against the team's existing SAB timings, and building the render config. Triggers on "new project", "make the scripture video", "generate the timing file", "compare with SAB".
---

# Scripture video, start to finish

Takes one project folder of SAB assets to rendered MP4s. Written so any model can
follow it verbatim; every command below has been run for real against this repo.

## 0. Establish the facts (never assume them)

Look at the project folder and fill in this table before running anything. Getting
these five wrong is the only way this process fails.

| Variable | How to find it | Example |
| :-- | :-- | :-- |
| `USFM` | the one `.SFM` in the project root | `src/tcy-mav/42MRKTCYMAV.SFM` |
| `BOOK` | `\id` line of the USFM, first word only | `MRK` |
| `AUDIO_PAT` | `ls <project>/audio` — note where the chapter number sits | `B02___{NN}_Mark________TCYNLCP1DA.mp3` |
| `LEVEL` | `\level` line of any existing SAB timing file | `phrase` |
| `LANG` | ISO-639-3 of the **script**, not the dialect | `mal` |

Two traps, both real:

- **`--level` must match the SAB files.** If SAB says `\level phrase`, aligning at
  `verse` produces segment ids (`2`) that cannot be compared to SAB's (`2a`,`2b`) —
  the comparison silently reports almost nothing matched.
- **Chapter inference takes the *first* number in the audio filename.** For
  `B02___01_Mark...` that is `02`, for all 16 files. Pass `--chapter` explicitly
  unless the filename is bare (`01.mp3`). Cheap check: does the stem start with a
  number? If not, pass `--chapter`.

`LANG` only feeds uroman's romanizer. For Malayalam-script text use `mal` even if the
language is Tulu/Mavilan — the dialect code changes nothing, the script code does.

## 1. Confirm the toolchain

```powershell
vidx --version
python -c "import onnxruntime, uroman; print('align extra OK')"
ffmpeg -version
```

Missing align extra → `pip install -e ".[align]"`. First alignment downloads a
340 MB model to `~/.vidx/mms-aligner/`; once only, then it works offline.

## 2. Pilot ONE chapter

Never loop before one chapter has been aligned *and* scored. A wrong `--level` or
`--chapter` wastes 12 minutes otherwise.

```powershell
vidx --align --usfm <USFM> --audio "<project>/audio/<AUDIO_PAT for ch 1>" `
     --lang <LANG> --chapter 1 --level <LEVEL> -y
```

Output lands at `<project>/timing/<BOOK>-01-timing.txt` — a sibling `timing/` folder
next to `audio/`, which is exactly the SAB layout. The name differs from SAB's
(`C01-01-MRK-01-timing.txt`), so nothing is overwritten and both sets coexist.

## 3. Score the pilot against SAB

```powershell
python scripts/benchmark_align.py --compare-only `
    --ref-dir <project>/timing --book <BOOK> --chapters 1 --level <LEVEL>
```

`--compare-only` reads timing files off disk — no model, no audio, no ffmpeg, instant.
It pairs `<BOOK>-NN-timing.txt` (VIDX) with `C##-##-<BOOK>-NN-timing.txt` (SAB) in the
same folder.

Read the table like this:

| Signal | Healthy | If not |
| :-- | :-- | :-- |
| Median | ≤ 0.25 s | wrong `--level`, or narrator skips `\s` headings → try `--no-headings` |
| `<=0.5s` | ≥ 90 % | same as above |
| Matched | close to row count | near-zero means the segment ids don't line up — `--level` mismatch |
| Verse 1 | often 0.5–1.5 s late | expected: spoken chapter announcement, not a bug |
| Last-verse end | negative, varies per chapter | expected: SAB holds the last verse over closing music, VIDX stops at the last spoken word |

Only proceed when median and `<=0.5s` look healthy.

## 4. Align the rest

```powershell
2..16 | ForEach-Object {
    $ch = "{0:d2}" -f $_
    vidx --align --usfm <USFM> --audio "<project>/audio/<AUDIO_PAT with $ch>" `
         --lang <LANG> --chapter $_ --level <LEVEL> -y
}
```

Roughly 8–12× realtime on CPU — about 40 s per 8-minute chapter, ~12 min for a Gospel.
Run it in the background and score the whole book when it finishes:

```powershell
python scripts/benchmark_align.py --compare-only `
    --ref-dir <project>/timing --book <BOOK> --chapters 1-16 --level <LEVEL>
```

## 5. Decide which timings the video uses

The comparison is a **quality gate, not a merge**. Both files sit in `timing/`, so
state the choice explicitly rather than defaulting.

**First check whether SAB timed the section headings.** Many SAB projects did not,
and it changes the answer:

Save this as `check_headings.py` and run it on both files:

```python
import sys
from pathlib import Path

for f in sys.argv[1:]:
    ids = [r.split("\t")[2] for r in
           Path(f).read_text(encoding="utf-8-sig").splitlines() if r.count("\t") == 2]
    print(Path(f).name, "->", [i for i in ids if i.startswith("s")] or "NO heading segments")
```

```powershell
python check_headings.py <project>/timing/C01-01-<BOOK>-01-timing.txt `
                         <project>/timing/<BOOK>-01-timing.txt
```

If SAB has none but VIDX produced `s1`, `s2`, …, then the narrator reads the headings
and SAB's contiguous verse rows silently absorb that audio — the wrong text sits on
screen for ~2 s at every heading, and the `heading` style never fires. Confirm by
checking which SAB rows straddle each VIDX `s` segment.

- **SAB has heading segments and scored well** → render from SAB's; hand-checked,
  and the agreement just proved the aligner didn't drift.
- **SAB has no heading segments** → prefer VIDX's. If the verses agree to ~0.2 s, the
  VIDX set is strictly better: same verse accuracy plus timed headings. Tell the user
  this explicitly — it is easy to default to SAB's and ship the desync.
- **No SAB timings at all** (the normal case for `--align`) → render from VIDX's.
- **A few chapters scored badly** → fix those in Audacity, keep the rest:
  ```powershell
  vidx --timing <file> --to-labels labels.txt   # Audacity: File > Import > Labels
  vidx --timing <file> --from-labels labels.txt # after File > Export > Export Labels
  ```

## 6. Build the render config

Copy `examples/bcab-mrk.yaml` and change only what the project needs: `project.name`,
`output_dir`, `style.*.font`, a background (`src/mal/3840x2160.mp4` for 16:9,
`src/mal/1080x1920.mp4` for Shorts), an optional `video.watermark` block for the
project's `logo.png`, and one `jobs:` entry per chapter pairing `usfm` + `timing` +
`audio` + `output`. One USFM serves the whole book.

**Fonts must exist on the rendering machine** — a missing family silently falls back to
a default that cannot shape Indic conjuncts. List what is actually available:

```powershell
Add-Type -AssemblyName System.Drawing
(New-Object System.Drawing.Text.InstalledFontCollection).Families |
    Select-Object -ExpandProperty Name |
    Where-Object { $_ -match 'Nirmala|Manjari|Noto|Bailey|Anjali' }
```

Generate the `jobs:` list from disk rather than typing it — SAB audio filenames carry
long underscore runs (`B02___01_Mark________TCYNLCP1DA.mp3`) that are easy to get
wrong. Glob for `audio/*{NN}_*.mp3` and `timing/<BOOK>-{NN}-timing.txt` per chapter,
then assert every path exists before rendering.

### Verify in three escalating steps

Never go straight to the full run.

```powershell
vidx -c <config>.yaml --generate-only --format ass   # ~0.2s: does the text parse?
vidx -c <config>.yaml -t 15 -y                       # ~20s: does it look right?
vidx -c <config>.yaml --gpu -y -w 4                  # full run, ~11x realtime on GPU
```

After the 15-second pass, **look at an actual frame** — this is the only step that
catches broken font shaping, an oversized watermark, or subtitles running off-canvas:

```powershell
ffmpeg -y -ss 8 -i output/<dir>/<first>.mp4 -frames:v 1 frame.png
```

Check: conjuncts formed correctly, verse reference legible, watermark sized and
positioned sanely, text inside the safe area.

## 7. Publish (optional)

Each batch writes `publish_manifest.json` beside its output. Uploading is a separate,
resumable step: `vidx --manifest output/<dir>/publish_manifest.json`. Needs the
`youtube` extra; see `docs/publishing_guide.md`.

## Reference

- `docs/alignment_guide.md` — timing generation, accuracy figures, troubleshooting
- `docs/configuration_guide.md` — full YAML reference
- `scripts/benchmark_align.py` — the scorer used in steps 3 and 4
