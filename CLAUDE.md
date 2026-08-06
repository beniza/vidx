# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -e ".[test]"              # base + pytest
pip install -e ".[align,youtube]"     # optional extras (see below)

pytest                                # full suite (testpaths=tests, ~70 tests)
pytest tests/test_align.py            # one file
pytest tests/test_cli.py::test_cli_version   # one test
pytest -k "timing"                    # by name

flake8 vidx/ --ignore=E501,E203,W503,W293,E226   # exactly what CI runs

pyinstaller --clean vidx.spec         # -> dist/vidx.exe
```

CI (`.github/workflows/tests.yml`) runs flake8 then pytest on Python 3.10/3.11/3.12.
Match the ignore list above or CI will disagree with local runs.

**Extras are not optional in practice.** `--align` needs `[align]` (onnxruntime +
uroman); `--publish`/`--manifest` need `[youtube]`. `vidx.spec` pulls Google modules
via `collect_submodules('google.auth')`, which returns an **empty list without
error** when the extra is absent — the build succeeds and the .exe then dies at
runtime with `No module named 'google'`. Install `[youtube]` before building, and
test the artifact.

## What this is

VIDX turns three Bible-translation assets into subtitled video or standalone
subtitles:

1. **USFM** scripture text (one `.SFM` can hold a whole book)
2. **Audio** narration, one file per chapter
3. **Timing map** — verse/phrase start+end times, normally produced by Scripture
   App Builder (SAB), or generated here with `--align`

## Architecture

Pipeline: `cli` → `config` → `batch_runner` → (`usfm_parser` + `ass_generator`) →
`ffmpeg_builder` → optionally `manifest` → `youtube`.

- **`batch_runner.py`** (largest, ~1070 lines) is the orchestrator and where most
  cross-cutting behaviour lives: job construction from YAML, per-job overrides,
  background preprocessing/caching, parallel workers, and manifest emission.
  Start here when tracing "why did the render do X".
- **`usfm_parser.py`** — native USFM 3.0 parser. Strips `\f`, `\x`, `\fig`; handles
  `target_chapter` selection so one `.SFM` serves every chapter.
- **`ass_generator.py`** — builds the `.ass`/`.srt`. Owns all styling decisions.
- **`ffmpeg_builder.py`** — composes filter graphs; GPU autodetect (NVENC/QSV).
- **`align.py`** — forced alignment via Meta MMS-300M-1130 (Wav2Vec2 CTC) through
  ONNX Runtime, no PyTorch. Text is romanized with uroman first, which is why it
  spans scripts rather than a fixed language list. Model (~340 MB INT8) downloads
  once to `~/.vidx/mms-aligner/`. **CC-BY-NC 4.0** — deliberately not bundled in the
  .exe, since VIDX itself is MIT.

### Two CLI modes

Config-driven (`-c file.yaml`, a `jobs:` list) and single-job (`--usfm --timing
--audio -o`). Anything applied to jobs must be handled in **both** paths —
`tag_test_duration` is the current example.

## Non-obvious invariants

These cost real time to rediscover.

**Timing files.** The body is byte-for-byte an Audacity label track
(`start\tend\tsegment_id`), which is why `--to-labels`/`--from-labels` work with no
special editor. Two naming conventions coexist in one `timing/` folder: SAB writes
`C##-##-BOOK-NN-timing.txt`, VIDX's `--align` writes `BOOK-NN-timing.txt`. Nothing
overwrites anything, and `scripts/benchmark_align.py` pairs them to score accuracy
(`--compare-only` scores files already on disk — no model, no audio, instant).

**`--level` must match the reference.** Verse level yields ids like `2`; phrase
level yields `2a`,`2b`. Compare across levels and almost nothing matches — the
scorer reports near-zero matches rather than raising.

**Chapter inference takes the first number in the audio filename.** Fine for
`01.mp3`; wrong for SAB exports like `B02___01_Mark...` (yields `02` for every
chapter). Pass `--chapter` unless the stem starts with the number.

**Section headings.** `\s` headings are timed as `s1`,`s2`,… by default because
narrators normally read them aloud. Many SAB timing files omit them entirely; when
they do, the heading audio gets absorbed by the straddling verse rows and the
heading style never fires. Check before choosing a timing set.

**ASS styling layers differ.** Only `verse` and `heading` read `background_box`.
Every `Overlay*` style is emitted with BorderStyle 1 and a transparent BackColour,
hardcoded — overlay text is outline-only and there is no key to change that. The
overlay divider hardcodes size 24 and inherits `title_color`. The overlay
`subtitle` is written into the `.ass` **verbatim**, while `title` passes through
`clean_subtitle_text` — so ASS override tags (colour, vector drawings via `\p1`)
survive in the subtitle only.

**libass ignores MarginV for middle alignments (4/5/6).** Two elements at
alignment 5 render on top of each other. Vertical offset requires a top/bottom
alignment plus a margin.

**All overlay text shares one `duration`.** A title card and a persistent
watermark cannot have different lifetimes within the overlay block; the
`video.watermark` image is a separate FFmpeg overlay and always runs full length.

**Background preprocessing.** A nonzero `loop_crossfade_sec` forces preprocessing
even for already-1080p clips (otherwise it is skipped when the source is already
within the target). Results cache under the output dir; deleting that cache costs
minutes on the next run.

## Conventions

- **TDD is a standing rule** (`docs/todo.md`): test first for features, fixes, and
  refactors. Open work lives as GitHub issues, not in `todo.md`.
- **No media is tracked.** `.gitignore` has `*.mp*` and `output/`. SFM, timing
  text, and small PNGs are tracked; audio and video live outside git.
- `src/<lang>/` holds scripture data, not code. `pyproject.toml` pins
  `packages = ["vidx"]` because setuptools' auto-discovery otherwise mistakes
  `src/` for a src-layout project and builds an empty wheel.
- Docs worth reading before changing behaviour: `docs/alignment_guide.md`,
  `docs/configuration_guide.md`, `docs/publishing_guide.md`.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
- Author a backlog-ready spec/issue → invoke /spec
- Take a Scripture project from SAB assets to rendered video → invoke /scripture-video
