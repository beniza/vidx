# Session Summary — Luke/John/Acts GPU Production & YouTube Publishing

Dev session covering 2026-07-13 to 2026-07-14. Scope: GPU-render three new books
(Luke, John, Acts — Sindhi Audio Bible), package a standalone exe, wire up and
debug the YouTube publishing workflow for a client-owned channel, and analyze
the resulting production run for workflow improvements. See `docs/todo.md` for
the actionable follow-ups this session generated.

## What shipped

**Rendering**
- Confirmed the single-chapter and full-book GPU render commands (`--gpu`,
  `-w 4`) against `luke.yaml` and, once created, `acts.yaml`/`john.yaml`.
- Downscaled all 9 background videos from 4K to 1080p via a one-off ffmpeg
  batch (`h264_nvenc`), since several exceeded the project's target
  resolution.
- Randomized background-video assignment across all three books' batch
  configs (shuffled blocks of all 9 videos per book, replacing the old fixed
  1-5 repeating cycle), then corrected the file paths after the `_1080p`
  suffix was dropped during manual file cleanup.
- Fixed a real bug: background video audio could leak into the final output
  in the non-watermark render branch, since only `-map "1:a"` (present when a
  watermark/title/outro triggers the explicit-map branch) excluded it. Fixed
  by passing `-an` on the background input so its audio is dropped at the
  demuxer regardless of branch (`vidx/ffmpeg_builder.py`).
- Fixed a config typo in `john.yaml`: `fsubtitle_position` (should be
  `subtitle_position`) was silently falling back to the wrong default overlay
  alignment (top instead of middle, under the title).

**Packaging**
- Built `dist/vidx.exe` via the existing `vidx.spec` (PyInstaller) so the
  client/team can run VIDX without a Python install. Verified GPU rendering
  and single-audio-stream output end-to-end through the exe.

**YouTube publishing**
- Walked through the "2-stage publishing" model (render writes an outbox
  manifest; a separate `--manifest` step uploads, resumable across quota
  pauses).
- Advised on granting upload access without sharing account credentials —
  initially recommended YouTube Studio channel permissions (Editor/Manager),
  then corrected: that newer Studio-only permission system does **not**
  carry OAuth/API access at all (confirmed via web search) — only classic
  Brand Account delegation, or Owner-role in some cases, actually works for
  third-party API uploads. Fallback path taken: the client authenticated
  their own `client_secrets.json` + `youtube_token.json` and handed the
  token file over directly.
- Fixed a real bug: the OAuth token cache path was hardcoded to the global
  `~/.vidx/youtube_token.json`, so authenticating for one project/channel
  would silently overwrite the cached login for every other project on the
  same machine. Now defaults to `<manifest's folder>/youtube_token.json`,
  overridable via `publishing.token_file` (`vidx/cli.py`, with new tests in
  `tests/test_cli.py`).

**Version control**
- Committed all of the above in five logically-separated commits (see `git
  log`). Along the way, caught and excluded ~4.8GB of raw source media (wav/
  zip/mp3/mp4 under `src/snd/sindhi-audio-bible-artifacts/`) from git via an
  updated `.gitignore`, keeping only the ~555KB of actual config/timing/text
  data. Also caught and deliberately did **not** commit
  `src/snd/upload_history.md` — a raw terminal scrollback capture containing
  a live OAuth `client_id` and every uploaded video's YouTube ID.

## What we learned from analyzing `upload_history.md`

- **The real bottleneck is Google's daily quota, not upload speed.** Every
  publish run stopped at exactly 5 successful uploads (~1650 units/video
  average) before tripping VIDX's 9500-unit safety guard — consistent with
  Google's ~10,000-unit default daily project quota. The user manually
  re-ran `vidx --manifest ...` roughly 17 times across the three books to get
  everything published.
- **`-w 4` GPU rendering doesn't scale linearly.** Solo chapters rendered in
  54-75s; the same book in a 4-worker batch averaged 120-150s/chapter — most
  likely NVENC encoder session contention on a single physical GPU encoder.
- **No skip-existing-output logic.** Luke's 24 chapters were fully
  re-rendered twice in this session (interrupted/restarted batch), since
  `batch_runner.py` reprocesses every job in a config on every invocation.
- **Quota tracking is a client-side illusion.** `YouTubePublisher.quota_used`
  is an in-memory counter that resets to `0` every process start — it has no
  idea how much of the *real* Google-side daily quota has already been
  consumed. Re-running the publish command shortly after hitting the local
  safety stop let 5 more uploads through — not because Google's quota
  actually reset early, but because VIDX's own tracking has no memory across
  process restarts. This could theoretically let real usage exceed the
  actual account quota undetected; the authoritative source of truth is
  Google Cloud Console's Quotas/Metrics view, not VIDX's own reporting.
- Minor findings: a stray mis-encoded character silently broke `run.bat`
  once; the `RequestsDependencyWarning` packaging gap (previously deferred as
  cosmetic) is confirmed to print on every single exe invocation.

## Open thread going into next session

Feasibility of parallel (`-w`-style) upload workers was assessed and
documented (plan file `vivid-marinating-tome.md` from that conversation) —
confirmed possible, needs locking around manifest writes and the quota
counter, plus per-worker `service` instances. Explicitly **not** a fix for
the daily quota ceiling itself — see the persisted quota tracking and
scheduled-retry items in `docs/todo.md` § YouTube Publishing Reliability &
Throughput, which are the higher-leverage fixes. This is the next planned
implementation task.
