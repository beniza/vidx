# Code Health Report — vidx / usfm2vdo

Date: 2026-07-06 (refreshed)
Scope: full repo, ad-hoc audit (tests, mypy, flake8, CI, packaging, licensing, security)

**Composite: 8.7/10** — production-ready for its intended single-operator CLI use. Every gap from the first audit (CI, packaging, licensing) is now closed. No confirmed runtime bugs.

## Dashboard

| Category | Tool | Score | Status | Details |
|---|---|---|---|---|
| Tests | pytest | 10/10 | CLEAN | 44/44 passed; 8 test files for 8 modules (1:1 breadth) |
| Lint (CI policy) | flake8 | 10/10 | CLEAN | 368 → 0 under CI ignore set. All F-codes (unused imports/vars, redefinitions) fixed. Full flake8 shows only 26 `E501` + 3 whitespace, deliberately ignored |
| CI (test/lint) | GitHub Actions | 9/10 | GOOD | `tests.yml` runs pytest + flake8 on push/PR across Python 3.10/3.11/3.12. Docked 1: no ffmpeg integration test (see below) |
| Packaging | pyproject.toml | 10/10 | CLEAN | `setup.py` deleted; installed metadata correctly declares `pyyaml`, `rich`, `mutagen` |
| Licensing | LICENSE + pyproject | 10/10 | CLEAN | MIT `LICENSE` file + `license = {text = "MIT"}` in metadata |
| Type check | mypy | 7/10 | WARNING | 3 items, all benign (see "Type-checker noise") |
| Security | static audit | 8/10 | GOOD | No backdoors/RCE. 2 Medium filtergraph-injection findings, gated behind untrusted configs (see `security_review.md`) |

## Fixed since the first audit

- **Test/lint CI added** — `tests.yml` runs `pytest` + `flake8` on push/PR across a 3.10/3.11/3.12 matrix. Was the #1 gap.
- **Packaging fixed** — `setup.py` (which under-declared deps) deleted; `pyproject.toml` is the single source of truth. Installed metadata now lists all three runtime deps.
- **LICENSE added** — MIT, as a file and a metadata field.
- **Lint cleaned** — 368 flake8 findings down to 29 (and 0 under CI policy). Unused imports, unused vars, and the duplicate `re` import are all gone.
- **Python floor set** — `requires-python = ">=3.10"`, matching the CI matrix floor.

## Open items (none block the current use case)

### 1. CI tests are unit-only — FFmpeg render path untested (highest remaining priority)
The test job does not install ffmpeg, so the core function — building and running the render command in `ffmpeg_builder.py` / `batch_runner.py` — has zero end-to-end coverage. A regression in command construction would pass CI green. One smoke test that renders a ~1-second clip would close this.

### 2. Two Medium security findings unfixed
Documented in `docs/security_review.md`: FFmpeg filtergraph injection via watermark `position` (`ffmpeg_builder.py:169`) and unescaped quotes in `_clean_filter_path` (`ffmpeg_builder.py:46`). Not a blocker for an operator running the tool on their own files. **Is** a blocker if the tool ever ingests third-party configs (planned YouTube automation, a batch service).

### 3. No CHANGELOG
Release notes are hand-typed inline in `release.yml`. A `CHANGELOG.md` would decouple history from the workflow.

## Type-checker / linter noise (NOT runtime bugs)

Verified by reading the code — false positives or cosmetic:

- `bumpers.py:11` — `mutagen = None` in an `except ImportError` block. Idiomatic optional-import guard.
- `bumpers.py:164` — mypy flags `join` over `list[str | None]`. The `None`-typed labels are only appended when `has_intro`/`has_outro` are true, so never `None` at that point. False positive.
- `config.py:7` — missing `yaml` stubs. Silence with `pip install types-PyYAML`.
- 26× `E501` long lines + a few `W293`/`E203` — pure formatting, ignored by CI policy on purpose.

## Good signs

- Tests exist and pass (44/44)
- Dependencies pinned with lower bounds; single packaging source
- No bare `except:` (all catch `Exception` explicitly)
- Optional deps guarded — degrades gracefully instead of crashing
- No `shell=True`, no `eval`/`exec`, no network code, no obfuscation (see security review)
- No tracked binary bloat (media fixtures under `src/` are gitignored)
- No secrets or hardcoded absolute paths found

## Recommended next steps (priority order)

1. Add an ffmpeg smoke test to CI (render a 1s clip, assert output exists and is non-empty).
2. Fix the 2 Medium security findings before any third-party-config exposure.
3. `pip install types-PyYAML` + two `# type: ignore` comments to make mypy clean.
4. Add `CHANGELOG.md`; have `release.yml` read from it instead of inline echoes.

## Notes / low priority

- `requirements.txt` is now redundant with pyproject `dependencies` (release.yml installs both).
- This report is not wired into `mkdocs.yml` nav, so it stays internal unless added there.
