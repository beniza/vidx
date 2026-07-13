# Test Coverage Report — vidx / usfm2vdo

Date: 2026-07-06
Measured with `python -m coverage run -m pytest && coverage report -m` (coverage 7.13.5, 44 tests passing)

## Coverage: 67% overall (2433 statements, 804 missed)

| Module | Coverage | Weak spot |
|--------|----------|-----------|
| `config.py` | 98% | — |
| `ass_generator.py` | 85% | opacity/transparency parsing partly untested |
| `progress.py` | 76% | rich-panel rendering paths |
| `bumpers.py` | 73% | ffmpeg concat path (`43-81`) |
| `ffmpeg_builder.py` | 72% | watermark raw-position fallback, render error paths |
| `cli.py` | 62% | batch mode (`101-179`), flag combinations |
| `batch_runner.py` | 62% | parallel `run_all`, error aggregation (`353-400`, `489-516`) |
| `usfm_parser.py` | **52%** | **largest, most complex, least covered** (`563-837` block) |
| (external) `usfm-converter/validator.py` | 18% | NOT part of the `vidx` package — see findings below |

## What is tested well

The command-construction and parsing happy paths are solid unit tests:

- **FFmpeg command building** — pad/crop/stretch scaling, duration/lavfi black background, audio fades, watermark (known position), auto-codec detection with caching, and render progress parsing (mocked `Popen`). Tests assert on the argv list, which is the right unit-level approach.
- **USFM parsing** — `_clean_text` footnote/xref/fig stripping (including tag variations without spaces), verse/heading parsing, timing parsing, text segmentation, SRT generation.
- **Config** — defaults, recursive merge, `safe_load`.
- **Batch** — missing-input handling, progress event emission, background preprocessing (mocked subprocess).

Tests use `tmp_path` fixtures, `monkeypatch`, and `MagicMock` appropriately, and even build real `.wav` files for `get_media_duration`.

## Missing test cases (high → low value)

### 1. No end-to-end ffmpeg render (biggest gap)
Every test mocks `subprocess`. The actual ffmpeg command is never executed, so a filtergraph that real ffmpeg **rejects** passes CI green. This is the core function of the tool with zero real-execution coverage.
→ Add one smoke test that renders a ~1-second clip, skipped via `shutil.which("ffmpeg")` when ffmpeg is absent.

### 2. `usfm_parser.py:563-837` untested
The largest uncovered block: batch/multi-chapter processing, glob file discovery, the validator integration path, and the module `main()`. Untested edge cases:
- **Verse-range parsing** (`\v 1-3`)
- Missing chapter, empty verses
- Malformed timing lines
- **Segment-count mismatch** (timing entries ≠ text segments) — the most likely real-world data bug

### 3. Security-relevant paths untested
- Watermark raw `position` fallback (`ffmpeg_builder.py:169`) — the filtergraph injection vector from `security_review.md`. Tests only use the safe `"top-right"` keyword.
- `_clean_filter_path` single-quote / metacharacter escaping (`ffmpeg_builder.py:46`). Test only checks the drive-colon case.
- `output_dir` path traversal.

### 4. Config / malformed-input cases
- Malformed `resolution` (`"abc"`, `"1x2x3"`) → **uncaught `ValueError` crash** (`ffmpeg_builder.py:83`, `batch_runner.py:309`)
- Invalid YAML, missing required job fields
- Negative / zero `crf`, `fps`, `margin`
- Unknown `scaling_mode`

### 5. Batch concurrency
- `max_workers>1` parallel execution
- One job fails, others continue (failure isolation)
- Correctness of the failed / succeeded tally

### 6. CLI
- Mode-2 batch-from-YAML end to end
- `--generate-only`, `--format srt|both`
- The convoluted `--clean-ass` / `--keep-ass` logic at `cli.py:61` (worth a dedicated test — the expression is easy to get wrong)

### 7. ASS generator
- Opacity `0.0-1.0` and `0%-100%` parsing (the documented transparency feature)
- RTL / complex-script text
- Long-line wrapping

## Findings surfaced during this analysis

- **Hidden external dependency**: `usfm_parser.py:15` does `from validator import ...`, a module living in the sibling `usfm-converter/validator.py` directory — **not inside the `vidx` package**. It is `try/except ImportError` guarded, so `VALIDATION_AVAILABLE` is `False` in any packaged wheel or PyInstaller exe. The validation feature is therefore dead in distribution and entirely untested. Decide: vendor `validator.py` into `vidx/`, or drop the feature.
- **Version inconsistency**: `usfm_parser.py:22` declares `VERSION = "0.1.1-alpha"` while the package is `0.2.0` everywhere else (`pyproject.toml`, `vidx/__init__.py`). (The earlier `code_health_report.md` incorrectly listed versions as consistent — this corrects it.)

## Reproduce

```bash
pip install coverage
python -m coverage run -m pytest
python -m coverage report -m
```
