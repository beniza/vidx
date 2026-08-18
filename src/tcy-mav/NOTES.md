# tcy-mav (Mark, Mavilan Tulu in Malayalam script) — project notes

Config: `examples/tcy_mav_mark_16x9.yaml`. Process this project produced:
`.claude/skills/scripture-video/SKILL.md`.

Last touched 2026-08-18. Paused here to work on unrelated VIDX features.

## Open work

1. **Full render never confirmed run.** `vidx -c examples/tcy_mav_mark_16x9.yaml
   --gpu -y -w 4`. Until it runs, `publish_manifest.json` still points at the
   25-second test clips, all PENDING. Running `vidx --manifest ...` now would
   upload 25s stubs. Entries key on `{book}_Ch{NN}` and `add_or_update`
   overwrites, so the next full render rewrites them; there is no
   skip-if-exists guard.
2. **`EGM MEDIA` text watermark on bgvideo-2** (chapters 1, 4, 7, 11, 13, 16) is
   faint against pale sand. Its outline is hardcoded to 1px with shadow 0
   (`ass_generator.py:312`) and there is no `watermark_outline_*` key. Either
   raise `watermark_size`/`watermark_opacity`, or drop the text since
   `logo.png` already brands the corner for the full length.
3. **`project.text_copyright` and `project.audio_copyright` are unset**, so
   descriptions render those as empty lines.
4. **16 untracked `src/mal/mrk/timing/MRK-*.txt`.** They predate this project
   and were deliberately excluded to keep commits focused. Commit or delete.

## Decisions (do not re-litigate)

- **Use VIDX's own `--align` timings, not the team's SAB files.** SAB timed no
  `\s` heading segments. The narrator does read headings aloud, so SAB's
  contiguous verse rows absorb ~2s of heading audio at ~7 points per chapter and
  the heading style never fires. Verse starts agree with SAB to 0.16s median /
  89% within 0.5s over 1671 boundaries, so VIDX's set is the same accuracy plus
  working headings. The initial recommendation was SAB; reversed after
  inspecting the files.
- **`--level phrase` is mandatory here.** SAB's files are phrase level. Verse
  level yields ids (`2`) that cannot pair with SAB's (`2a`, `2b`) and the
  comparison silently reports near-zero matches rather than erroring.
- **Pass `--chapter` explicitly.** Chapter inference takes the *first* number in
  the audio filename; `B02___01_Mark...` yields `02` for all 16 files.
- **`--lang mal`** (script, not dialect). uroman romanizes identically for
  `mal`, `tcy`, and no lang, so it changes nothing here, but `mal` is the honest
  label for Malayalam-script text.
- **Backgrounds and music assigned by seeded shuffled round-robin** (seed
  20260804): 6/5/5 across bgvideo, 4/3/3/3/3 across bgmusic, no clip repeating
  in consecutive chapters. Pure random would likely have put one clip on 9
  chapters and another on 2.
- **`loop_crossfade_sec: 1.0`.** Clips run 12-22s against 8-minute chapters, so
  they loop 20-40 times. `batch_runner.py:586` confirms a nonzero crossfade
  forces preprocessing even for already-FHD clips, so all three get the seam
  dissolved, not just the 4K one.
- **The gold rule between title and wordmark is an ASS vector drawing inside the
  subtitle string**, not the built-in `divider_line`. The divider style
  (`ass_generator.py:313`) hardcodes size 24 and inherits `title_color`, so it
  can be neither thick nor gold-while-the-title-stays-white. The subtitle is the
  one overlay field written to the `.ass` verbatim (`ass_generator.py:402`)
  instead of through `clean_subtitle_text`, so override tags survive. A drawing
  needs no font support, unlike glyphs such as the box-drawing characters.
- **Subtitle is alignment 2 + `margin_v` 390, not position 5.** libass ignores
  MarginV for middle alignments (4/5/6), so a subtitle at 5 lands exactly on top
  of the title. Margin calibrated by rendering, not arithmetic:
  `rule_y = (1080 - M) - 60`.
- **`-t` filename tagging lives in `cli.py`, never in config `output:` values.**
  Baking `_25s` into the YAML would leak the tag into final renders too.
- **Media stays untracked.** `.gitignore:55` has `*.mp*`. Tracked here: SFM,
  timing text, `logo.png`, config.
- **Verse and heading `background_box: false`** by user choice; all text is
  outline-only. Verse `outline_width` is still 3 while the overlay uses 4, so
  the upper lines of long verses over bright footage look weak. Left as-is.

## Traps

- **Do not casually delete `output/tcy_mav_mrk/.cache`.** 158MB of
  crossfade-baked background loops, several minutes to rebuild.
- **YouTube chapter markers:** 15/16 chapters satisfy YouTube's rules (>=3
  chapters, >=10s apart, first at 0:00). Chapter 5 has only 2 headings so it
  gets none. Chapter 9's first heading starts at 22.06s and needs a 0:00 anchor
  inserted or YouTube rejects the whole list.
- **Verify which `.ass` you are inspecting.** After outputs were renamed with
  `_25s`, `Mark_Chapter_01.ass` sorts *before* `Mark_Chapter_01_25s.ass`, so
  `ls ... | head -1` grabs the stale file and makes a working feature look
  broken. Stale unsuffixed files have been deleted, but the sort order trap
  returns with every new suffix.
- **The em dash in manifest titles was never broken.** Reported as mojibake, but
  the bytes are `\xe2\x80\x94`, correct UTF-8. The `?` came from printing
  through a cp1252 Windows console. `manifest.py:134` writes utf-8 with
  `ensure_ascii=False`. No fix was needed or made.
- **Worst-case verse block is 3 wrapped lines** (Mark 14:57-58, 267 chars),
  ~277px tall. An earlier 5-line estimate was wrong: real wrap width is ~89
  chars/line at 48px Manjari, not 62.
