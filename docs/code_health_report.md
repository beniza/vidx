# Code Health Report — vidx / usfm2vdo

Date: 2026-07-06
Scope: full repo, ad-hoc audit (tests, mypy, flake8, black, CI, packaging, licensing)

**Composite: 6.4/10** — works and is tested, but has packaging, CI, and licensing gaps before "production ready." No confirmed runtime bugs.

## Dashboard

| Category | Tool | Score | Status | Details |
|---|---|---|---|---|
| Tests | pytest | 10/10 | CLEAN | 44/44 passed |
| Type check | mypy | 7/10 | WARNING | 3 errors, all benign (see "Type-checker noise" below) |
| Lint | flake8 | 0/10 | CRITICAL (mostly noise) | 368 findings — 285 trailing whitespace, 62 long lines. Real-but-cosmetic: 5 unused imports, 2 unused exception vars, 1 duplicate `re` import |
| Formatting | black | — | not adopted | 9/9 files would reformat — no formatter enforced; not itself a defect |
| CI (test/lint) | GitHub Actions | 0/10 | GAP | `docs.yml` + `release.yml` only. **No workflow runs tests or lint on push/PR.** A broken PR can merge clean. |
| Packaging | setup.py vs pyproject.toml | 4/10 | GAP | Both exist and disagree; built metadata is missing 2 declared deps (see below) |
| Licensing | — | 0/10 | GAP | **No LICENSE file, no license field in metadata** |

## Confirmed issues worth acting on

### 1. No test/lint CI (highest priority)
Only `docs.yml` (GitHub Pages) and `release.yml` (tagged builds) exist. Nothing runs `pytest` on push or PR. A regression can merge without anyone noticing. One workflow file fixes this — biggest risk reduction available.

### 2. Packaging: setup.py and pyproject.toml disagree
`pyproject.toml` declares `pyyaml`, `rich`, `mutagen`. `setup.py` declares only `pyyaml`. The actual built metadata proves the disagreement leaks through:

```
vidx.egg-info/PKG-INFO → Requires-Dist: pyyaml>=5.4.1   (rich and mutagen absent)
```

Impact is **degraded, not broken**: both `rich` and `mutagen` are `try/except ImportError` guarded (`progress.py:89`, `bumpers.py:9`), so a missing dep silently drops progress bars / falls back to ffprobe rather than crashing. Still, users get a worse experience with no signal why.

Fix: delete `setup.py` and rely solely on `pyproject.toml` (single source of truth), then regenerate the egg-info.

### 3. No LICENSE
No `LICENSE` file and no `license` field in `pyproject.toml`/`setup.py`. For a Bridgeconn/SIL scripture tool intended for distribution, this blocks legitimate reuse. Add the intended license (e.g. MIT) as a file and a metadata field.

### 4. No CHANGELOG
Release notes are hand-typed inline in `release.yml` (lines 45–71). A `CHANGELOG.md` would decouple history from the workflow and reduce drift.

## Type-checker / linter noise (NOT runtime bugs)

Verified by reading the code — these are false positives or cosmetic, safe to leave or clean at leisure:

- `bumpers.py:12` — `mutagen = None` in an `except ImportError` block. Idiomatic optional-import guard, not a bug.
- `bumpers.py:153` — mypy flags `join` over `list[str | None]`. The `None`-typed labels (`intro_label`, `outro_label`) are only appended when `has_intro`/`has_outro` are true, so they are never `None` at that point. False positive.
- `batch_runner.py:10` + `:133` — `re` imported at top (unused there) and re-imported locally where it is actually used. Redundant, works fine. Drop the top-level import.
- 285× `W293` trailing whitespace on blank lines + 62× `E501` long lines — pure formatting. `black vidx/` or `autopep8` clears these in one pass.

## Good signs

- Tests exist and pass (44/44)
- Dependencies pinned with lower bounds
- No bare `except:` (all catch `Exception` explicitly)
- Optional deps guarded — degrades gracefully instead of crashing
- No tracked binary bloat (media fixtures under `src/` are gitignored)
- Version strings consistent across `pyproject.toml`, `setup.py`, `vidx/__init__.py` (all `0.2.0`)
- No secrets or hardcoded absolute paths found
- `.egg-info`, `build/`, `dist/`, `output/`, `site/` all correctly gitignored (0 tracked)

## Recommended fix order

1. Add a CI workflow running `pytest` (and ideally `flake8`) on push/PR.
2. Add a `LICENSE` file + `license` metadata field.
3. Delete `setup.py`; make `pyproject.toml` the single packaging source; regenerate egg-info.
4. Add `CHANGELOG.md`; have `release.yml` read from it instead of inline echoes.
5. Run `black vidx/` once to clear ~350 cosmetic lint findings, then drop the 5 unused imports.

## Notes / low priority

- Python version is inconsistent across configs: `docs.yml` uses 3.10, `release.yml` uses 3.11, `pyproject.toml` says `>=3.7`, local tests ran on 3.12. Not breaking, but pick a supported floor and test it in CI.
- This report is not wired into `mkdocs.yml` nav, so it stays internal unless added there.
