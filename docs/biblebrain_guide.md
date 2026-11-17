# 🌍 Importing from Bible Brain
*Get the text, audio and (when available) verse timing for a Bible without a Scripture App Builder project*

---

## 💡 What Is This, and When Do I Need It? (The "WHY")

VIDX needs three things per chapter: the **text**, the **audio**, and a **timing file**. If your team built
a Scripture App in Scripture App Builder (SAB) you already have all three, and you can skip this page.

If you don't, **Bible Brain** (Faith Comes By Hearing's free Bible data service) may already hold them.
`vidx --biblebrain` lets you pick a Bible, downloads its text and audio, and writes a ready-to-run job file.

You need a free **Bible Brain API key**. Request one at <https://4.dbt.io/api_key/request>.

!!! warning "Check the licence before you publish"
    Bible Brain states that downloaded content must stay within the application the key was issued for.
    Rendering a video and uploading it to YouTube can go beyond that for some Bibles. Confirm the
    rights for the Bible you choose before publishing.

---

## 🚀 The Easy Way: Follow the Prompts

```bash
vidx --biblebrain
```

VIDX asks for, in order:

1. **Your API key** (hidden as you type). Or set the `BIBLE_BRAIN_KEY` environment variable and it won't ask.
2. **Country**, then **language**. Only languages that have a Bible with **both text and downloadable audio**
   are shown, so you never pick something VIDX cannot use.
3. **Bible**, then the **book** (e.g. `MRK`, `1CO`) and the **chapters** (a number, a range, or `all`).
4. **Timing.** If Bible Brain has verse timing for this Bible you are asked whether to use it.

You end up with:

```
bb_import/
├── bb_jobs.yaml                 ← the file you give to VIDX
└── src/MALMAL/
    ├── MRK-01.usfm              ← text, one file per chapter
    ├── 01_MRK.mp3               ← audio
    └── MRK-01-timing.txt        ← timing (only when you chose Bible Brain timing)
```

Then render exactly as usual:

```bash
vidx -c bb_import/bb_jobs.yaml --bg src/bg.mp4
```

---

## 🤖 Scripting a Whole Book (No Prompts)

Add `--bb-bible` and nothing is ever asked, which suits batch files and servers. The key must come from
`BIBLE_BRAIN_KEY`.

```bash
# Whole book, using Bible Brain timing when it exists
vidx --biblebrain --bb-bible MALMAL --bb-book MRK

# A range, and force VIDX timing
vidx --biblebrain --bb-bible MALMAL --bb-book 1CO --bb-chapters 1-4 --bb-timing vidx
```

| Option | Meaning |
| :--- | :--- |
| `--bb-bible ID` | The Bible to import (e.g. `MALMAL`). Turns scripted mode on. |
| `--bb-book BOOK` | Book code. Required in scripted mode. |
| `--bb-chapters SPEC` | `all` (default), `5`, `1-5`, or `1,3,5-7`. `all` stops when the book ends. |
| `--bb-language ISO` | Language code to look the Bible up in. Optional, but can make the lookup more precise. |
| `--bb-timing` | `biblebrain`, `vidx`, or `auto`. Scripted runs default to `auto` (Bible Brain when available). |
| `--bb-out FOLDER` | Where files go. Default `bb_import`. |
| `--bb-refresh` | Ignore the saved lists and fetch them again (see below). |

A chapter that cannot be imported (for example, it has no timing) is reported and the rest carry on. The
command exits with **1** if any requested chapter failed, so scripts can tell.

---

## ⏱️ Which Timing Should I Use?

| Choice | When it fits |
| :--- | :--- |
| **Bible Brain timing** | Fastest. Available only for some Bibles, and usually at verse level. |
| **VIDX timing** | Not available from Bible Brain, or you want phrase-level timing. Use your SAB files, or run `vidx --align` (see the [Timing File Guide](alignment_guide.md)). |

When you choose VIDX timing, the timing files do not exist yet. VIDX prints the exact `vidx --align` command
for each chapter, and the files it creates land where `bb_jobs.yaml` already expects them.

---

## ⚡ Faster Repeat Runs (The Saved Lists)

Finding which languages have text and audio takes one request per language, which can take minutes the first
time. VIDX saves the country, language and Bible **lists** for 7 days in `~/.vidx/biblebrain-cache.json`, so
the next run is instant. Only these lists are saved: never your key, the text, or the audio.

- Want fresh lists? Add `--bb-refresh`.
- Want the file somewhere else? Set `VIDX_BB_CACHE` to a path.

---

## 🩺 Troubleshooting

| What you see | What to do |
| :--- | :--- |
| `API key rejected by Bible Brain` | Check the key, or request a new one. |
| `Bible XXXXXX was not found` | Check the id; try adding `--bb-language`. |
| `does not have both text and downloadable audio` | That Bible cannot be turned into a video here. Pick another. |
| `No chapters found for ...` | Wrong book code for that Bible (it may not contain that book). |
| Chapters import but timing is missing | Bible Brain has no timing for it: use `--bb-timing vidx`. |

!!! note "Text comes without headings"
    Bible Brain text has no section headings or footnotes, so videos made this way show verses only. If you
    want headings on screen, add them to the USFM yourself before rendering.
