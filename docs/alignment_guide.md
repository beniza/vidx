# 🎯 VIDX Timing File Guide
*How to create the verse timing maps VIDX needs — automatically, from your audio*

---

## 💡 What Is a Timing File, and Why Do I Need One? (The "WHY")

VIDX needs to know **when** each verse is spoken in your audio recording so it can show the right
words on screen at the right moment. That information lives in a small text file called a **timing
file** (or "timing map"):

```
\id MRK
\c 16
\level verse
\separators . ? ! , ; :
12.000	23.300	1
23.300	30.500	2
30.500	37.330	3
```

Each line says *"from this second, to this second, show segment N"*. The header tells VIDX which
book and chapter it belongs to.

**If your team built a Scripture App in Scripture App Builder (SAB), you already have these files** —
use them directly and skip this whole guide. Look for a `timing/` folder containing files named
something like `C01-41-MRK-01-timing.txt`.

**If you don't have them**, you previously had three options, all awkward:

| Old approach | The problem |
| :--- | :--- |
| Mark them by hand in Audacity | Accurate, but roughly an hour of tedious work per chapter |
| Run **aeneas** | Last released in 2017, needs Python 3.5, and only supports 38 languages — not Malayalam or Sindhi |
| Record with **HearThis** | Only helps if you haven't recorded yet |

VIDX now generates them for you with `--align`, in about a minute per chapter, in **1130+
languages**.

---

## 🎯 What You Need (The "WHAT")

1. **Your USFM scripture file** — the same `.SFM` file you already render videos from.
2. **Your audio recording** for the chapter (`.mp3`, `.wav`, `.mpeg` — anything FFmpeg reads).
3. **The alignment extra installed**, one time only:

```powershell
pip install vidx[align]
```

The first time you run an alignment, VIDX downloads a speech model (**about 340 MB**) to
`C:\Users\YourUsername\.vidx\mms-aligner\`. This happens **once**. After that you can align offline,
forever, with no internet connection.

!!! note "About the model licence"
    The speech model is Meta's **MMS-300M-1130**, licensed **CC-BY-NC 4.0 (non-commercial)**.
    VIDX itself is MIT-licensed, and the model is downloaded at runtime rather than bundled, so
    nothing non-commercial ships inside VIDX. For ministry and translation use this is fine. If you
    intend to use VIDX commercially, talk to your team lead before using `--align`.

---

## 🛠️ How to Generate Timings (The "HOW")

### Step 1: Run the alignment

```powershell
vidx --align --usfm src/mal/42MRKMAL10RO.SFM --audio src/mal/mrk/audio/01.mp3 --lang mal
```

That's it. You'll see:

```
[*] Aligning 42MRKMAL10RO.SFM ch.1 against 01.mp3
    45 verse segments | 6.9 min audio | lang=mal
[+] Wrote 45 timings: src\mal\mrk\timing\MRK-01-timing.txt
```

### Step 2: Where the file is saved

VIDX saves timing files **inside your project, next to the audio they describe** — never in a
temporary folder. Specifically:

- If your audio is in a folder called `audio/`, the timing file goes into a sibling `timing/` folder
  (created if needed). This matches the layout SAB uses:
  ```
  src/mal/mrk/audio/01.mp3   ->   src/mal/mrk/timing/MRK-01-timing.txt
  ```
- Otherwise it is written **beside the audio file itself**.
- Pass `-o some/folder/` to choose a different folder, or `-o some/file.txt` for an exact filename.

VIDX will **never silently overwrite** an existing timing file — it asks first. Add `-y` to overwrite
without being asked. This protects timings you have already hand-tuned.

### Step 3: Render as usual

The generated file is an ordinary SAB-compatible timing file, so nothing else changes:

```powershell
vidx --usfm src/mal/42MRKMAL10RO.SFM --timing src/mal/mrk/timing/MRK-01-timing.txt --audio src/mal/mrk/audio/01.mp3
```

---

## ⚙️ Useful Options

| Option | What it does |
| :--- | :--- |
| `--lang mal` | ISO-639-3 language code. **Always pass this** — it noticeably improves accuracy. `mal` Malayalam, `snd` Sindhi, `hin` Hindi, `tam` Tamil, `eng` English. |
| `--chapter 5` | Set the chapter explicitly. Normally inferred from the audio filename (`01.mp3` → chapter 1). |
| `--book MRK` | Book code written into the `\id` header. Normally read from the USFM file. |
| `--level phrase` | Split verses at punctuation into `1a` / `1b` / `1c` segments, like SAB's phrase-level timings. Default is `verse`. |
| `--no-headings` | Skip `\s` section headings. See below. |
| `-o FOLDER` | Write somewhere other than the default location. |
| `-y` | Overwrite an existing timing file without asking. |

### Section headings

Most narrators **read section headings aloud** ("Jesus heals the sick"), so by default VIDX times
them as `s1`, `s2`, … segments — exactly as SAB does. Leaving them out makes the *following verse*
swallow the heading audio and drift late.

If your recording skips the headings and reads only verses, pass `--no-headings`.

---

## 🎚️ Fine-Tuning Timings in Audacity

Automatic alignment is very good but not perfect, and one or two verses per chapter may need a
nudge. **You don't need a special editor.** A timing file's body is byte-for-byte an Audacity
**label track**, so you can drag boundaries against the waveform:

### Step 1: Export as labels

```powershell
vidx --timing src/mal/mrk/timing/MRK-01-timing.txt --to-labels labels.txt
```

### Step 2: Edit in Audacity

1. Open Audacity and drag your **audio file** into the window.
2. Go to **File > Import > Labels…** and choose `labels.txt`.
3. You'll see every verse as a labelled region under the waveform. Drag any boundary to move it.
   The audio waveform makes it obvious where each verse actually starts.
4. Go to **File > Export > Export Labels…** and save back over `labels.txt`.

### Step 3: Merge your edits back

```powershell
vidx --timing src/mal/mrk/timing/MRK-01-timing.txt --from-labels labels.txt
```

Moving one boundary shifts the end of one verse and the start of the next together, so the file
always stays continuous with no gaps or overlaps.

---

## 📊 How Accurate Is It?

Measured against this project's existing SAB/aeneas timing files:

| Corpus | Boundaries | Median error | Within 1 second |
| :--- | :--- | :--- | :--- |
| Malayalam Mark, all 16 chapters | 678 | **0.23 s** | **99.1 %** |
| Sindhi Mark 5 (Arabic script) | 43 | **0.14 s** | 95 % |

Speed is roughly **8× realtime on CPU** — about a minute for a 7-minute chapter, or ~13 minutes for
a whole 16-chapter Gospel. No GPU needed.

For comparison, estimating verse positions from text length alone (no speech model) gives a median
error of 1.84 s — visibly out of sync, and requiring nearly every verse to be corrected by hand.

---

## ❓ Common Questions & Troubleshooting

### Q: It says "Alignment dependencies missing".
Run `pip install vidx[align]`. This applies to Python installs only — from v0.4.1 the standalone
`vidx.exe` has the aligner built in, so there is nothing to install. If you see this message when
running the `.exe`, you have a build older than v0.4.1; download a newer one.

### Q: My whole chapter is offset by a second or two at the start.
Many recordings begin with a spoken chapter announcement ("The Gospel of Mark, chapter one") that
isn't part of any verse. VIDX doesn't detect this yet, so verse 1 may be placed late. Nudge verse 1
in Audacity — the rest of the chapter is usually unaffected.

### Q: My last verse ends before the audio does — is that a bug?
No, that's deliberate. The last verse ends where the narration of its text stops, so closing music
or a spoken sign-off isn't covered by a subtitle. Note that SAB's own timing files usually *do*
stretch the last verse over that closing audio, so a VIDX file will legitimately end earlier than
the SAB equivalent for the same chapter. If you would rather hold the last verse to the end, drag
its boundary out in Audacity.

### Q: Every verse is late by roughly the same amount.
Check whether your narrator reads the section headings. If they do and you passed `--no-headings`
(or vice versa), the mismatch pushes everything along. Try flipping that option.

### Q: Can I align a whole book in one command?
Not yet — run one chapter at a time for now. In PowerShell you can loop:

```powershell
1..16 | ForEach-Object {
    $ch = "{0:d2}" -f $_
    vidx --align --usfm src/mal/42MRKMAL10RO.SFM --audio "src/mal/mrk/audio/$ch.mp3" --lang mal -y
}
```

### Q: Does my language have to be on a supported list?
Almost certainly not a problem. The model covers **1130+ languages**, and text is romanized before
alignment, so Devanagari, Arabic, Malayalam, Thai and Latin scripts all work the same way. If your
exact language code isn't recognised, omit `--lang` and it will still align — just slightly less
accurately.

### Q: Is my audio uploaded anywhere?
No. Alignment runs entirely on your own computer. The only network access is the one-time model
download.
