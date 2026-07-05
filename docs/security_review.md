# Security Review — vidx / usfm2vdo

Date: 2026-07-06
Scope: full repo, static audit (command injection, code exec, network/exfiltration, YAML
deserialization, FFmpeg filtergraph injection, path handling, ReDoS, supply chain)

## Verdict: No backdoors, no malware, no RCE

The loud indicators are all absent — verified, not assumed:

- **No network code** anywhere (`requests` / `urllib` / `socket` / `http` / `webbrowser`) — nothing phones home, no exfiltration path.
- **No dynamic code execution** — no `eval` / `exec` / `compile` / `__import__` / `pickle` / `marshal`.
- **No obfuscation** — no `base64` / hex / `codecs.decode` blobs.
- **No `shell=True`** — every `subprocess` call uses list-form argv (`ffmpeg_builder.py`, `bumpers.py`, `batch_runner.py`), so OS shell metacharacter injection is not possible.
- **YAML uses `yaml.safe_load`** (`config.py:89`) — no deserialization RCE (the classic PyYAML footgun).
- Entire git history is a single identity; no suspicious commits.

## Attack surface: FFmpeg filtergraph

argv is safe, but the tool builds filtergraph **strings** (`-vf` / `-filter_complex`) and
hands them to ffmpeg. ffmpeg's own filter parser is a second injection layer, and several
filters can read local files (`drawtext=textfile=`, `movie=`, `subtitles=`). That is where
the real risk lives.

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | **Medium** | `ffmpeg_builder.py:169` | Watermark `position` fallback assigns the **raw config string** to `xy_str`, injected directly into `overlay={xy_str}`. A crafted config injects arbitrary filter syntax → local file disclosure (embed a secret file into the rendered video via `drawtext`/`movie`) or DoS. |
| 2 | **Medium** | `ffmpeg_builder.py:46, 192, 199` | `ass='{path}'` — `_clean_filter_path` escapes backslashes and the Windows drive colon but **not single quotes** or filtergraph metacharacters (`:` `,` `[` `]`). A path containing `'` breaks out of the quoted string into the filtergraph. Subtitle paths are internally generated (lower risk), but `output_dir` / background paths from config flow into similar constructs. |
| 3 | Low–Medium | `config.py`, `batch_runner.py:322` | `output_dir`, `output_file`, `background_media`, `title_image`, etc. are used verbatim with `Path()` and no confinement. `output_dir: "../../.."` or an absolute path → arbitrary read/write wherever the process can reach. |
| 4 | Low | `ffmpeg_builder.py:83`, `batch_runner.py:309` | `map(int, res_str.split("x"))` raises `ValueError` on malformed `resolution` (e.g. `"abc"`, `"1x2x3"`); uncaught in `ffmpeg_builder` → crash. DoS-ish, not a security hole. |
| 5 | Low (future) | `docs/yt_integration_plan.md` | Planned OAuth token cached at `~/.vidx/youtube_token.json`. Not implemented yet. When built: `0600` perms, never log the token, keep the client secret out of the distributed `.exe`. |

## Threat model

For the current use — an operator running this on their own files — practical risk is
**low**; you would be attacking yourself. The moment configs or input paths come from a
third party (a batch service, a web frontend, or the planned YouTube automation ingesting
user manifests), items **1–3 become genuinely exploitable** and should be fixed first.

ReDoS was checked: the USFM parser regexes (`usfm_parser.py:37,40,46,50`) use lazy /
character-class-bounded quantifiers with no nested/overlapping repetition — no catastrophic
backtracking.

## Recommended hardening (for the two Medium findings)

1. `ffmpeg_builder.py:169` — whitelist `wm_pos`: if it is not a known keyword
   (`top-left`/`top-right`/`bottom-left`/`bottom-right`) and does not match a strict
   coordinate pattern (e.g. `^[\dWwHh:+\-*/. ()]+$`), fall back to a safe default instead
   of passing the raw string through.
2. `ffmpeg_builder.py:46` — in `_clean_filter_path`, also escape `'` → `\'` (and treat `:`
   inside the quoted filter argument), or validate that the resolved path contains no
   filtergraph metacharacters before interpolation.
3. (Optional) Wrap resolution parsing in `try/except` with a fallback to `1920x1080`
   (finding 4).

## Supply chain notes

- Dependencies use `>=` lower bounds only (`pyyaml`, `rich`, `mutagen`) — no upper bounds,
  no lockfile/hashes. A compromised future release of a dep would be pulled into the
  PyInstaller exe build. Consider a pinned lockfile for the released binary.
- `release.yml` uses `permissions: contents: write` (appropriate) and `secrets.GITHUB_TOKEN`
  (standard). Actions are pinned to major tags (`actions/checkout@v4`, `setup-python@v5`,
  `softprops/action-gh-release@v2`), not commit SHAs — minor supply-chain nit; pin to SHAs
  for defense in depth.

## Verification of this audit

- Pattern scans: `git grep` for `shell=True`, `eval(`, `exec(`, `pickle`, `yaml.load`,
  `import requests`/`urllib`/`socket`, `base64` — all clean except the safe uses noted above.
- Read in full: `config.py`, `ffmpeg_builder.py`, `bumpers.py`, `cli.py`, and the render /
  preprocess paths in `batch_runner.py`.
- No source files were modified by this review.
