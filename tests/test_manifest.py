from vidx.manifest import (
    resolve_metadata_template,
    ManifestEntry,
    ManifestManager,
    generate_offline_package,
    build_chapter_markers,
    usfm_book_name,
)

# Three headings, >=10s apart, with a merged verse in the middle section.
CH_USFM = """\\id MRK
\\h മർക്കോച്ച്
\\c 1
\\s First section
\\v 1 One.
\\v 2 Two.
\\s Second section
\\v 3-4 Three and four.
\\v 5 Five.
\\s Third section
\\v 6 Six.
"""
CH_TIMING = """\\c 1
\\level verse
0.5\t3.0\ts1
3.0\t20.0\t1
20.0\t40.0\t2
40.0\t42.0\ts2
42.0\t70.0\t3-4
70.0\t95.0\t5
95.0\t97.0\ts3
97.0\t130.0\t6
"""


def _write(tmp_path, usfm=CH_USFM, timing=CH_TIMING):
    u = tmp_path / "b.SFM"
    t = tmp_path / "MRK-01-timing.txt"
    u.write_text(usfm, encoding="utf-8")
    t.write_text(timing, encoding="utf-8")
    return str(u), str(t)


def test_resolve_metadata_template():
    tmpl = "{book} Chapter {chapter:02d} — {language}"
    res = resolve_metadata_template(tmpl, book="Mark", chapter=3, language="Sindhi")
    assert res == "Mark Chapter 03 — Sindhi"

    # Missing key fallback
    tmpl_missing = "{book} Chapter {chapter} by {author}"
    res_missing = resolve_metadata_template(tmpl_missing, book="John", chapter=1)
    assert res_missing == "John Chapter 1 by {author}"

    # extra kwargs reach the template, which is how {chapters} and {h} arrive
    assert resolve_metadata_template(
        "{h} {ch}\n{chapters}", h="മർക്കോച്ച്", ch=1, chapters="0:00 A"
    ) == "മർക്കോച്ച് 1\n0:00 A"


def test_usfm_book_name_reads_h(tmp_path):
    u, _ = _write(tmp_path)
    assert usfm_book_name(u) == "മർക്കോച്ച്"
    plain = tmp_path / "noh.SFM"
    plain.write_text("\\id MRK\n\\c 1\n\\v 1 One.\n", encoding="utf-8")
    assert usfm_book_name(str(plain)) == ""


def test_chapter_markers_labels_headings_with_verse_ranges(tmp_path):
    u, t = _write(tmp_path)
    # first heading starts at 0.5s, so it collapses to 0:00 rather than adding an intro
    assert build_chapter_markers(u, t) == (
        "0:00 First section (1:1-2)\n"
        "0:40 Second section (1:3-5)\n"
        "1:35 Third section (1:6)"
    )


def test_chapter_markers_synthesise_an_intro_when_the_first_heading_is_late(tmp_path):
    # Mark 9's real shape: verse 1 precedes the first heading.
    timing = CH_TIMING.replace("0.5\t3.0\ts1", "22.0\t25.0\ts1").replace(
        "3.0\t20.0\t1", "1.0\t22.0\t1"
    )
    u, t = _write(tmp_path, timing=timing)
    out = build_chapter_markers(u, t, intro_label="മർക്കോച്ച് 1:1")
    assert out.splitlines()[0] == "0:00 മർക്കോച്ച് 1:1"
    assert out.splitlines()[1].startswith("0:22 First section")


def test_chapter_markers_respect_the_bumper_offset(tmp_path):
    u, t = _write(tmp_path)
    out = build_chapter_markers(u, t, offset_seconds=30.0).splitlines()
    # A 30s intro pushes the first heading to 0:30, past the 10s collapse
    # threshold, so it no longer owns 0:00 and a synthetic marker appears.
    assert out[0] == "0:00 Introduction"
    assert out[1].startswith("0:30 First section")
    assert out[2].startswith("1:10 Second section")   # 40s + 30s
    assert out[3].startswith("2:05 Third section")    # 95s + 30s

    # A short intro folds into the first heading's chapter instead
    short = build_chapter_markers(u, t, offset_seconds=5.0).splitlines()
    assert short[0] == "0:00 First section (1:1-2)"


def test_chapter_markers_returns_empty_when_youtube_would_reject(tmp_path, capsys):
    # only two headings -> below YouTube's 3-marker minimum
    usfm = "\\id MRK\n\\c 1\n\\s A\n\\v 1 One.\n\\s B\n\\v 2 Two.\n"
    timing = "\\c 1\n\\level verse\n0.5\t3.0\ts1\n3.0\t40.0\t1\n40.0\t42.0\ts2\n42.0\t90.0\t2\n"
    u, t = _write(tmp_path, usfm=usfm, timing=timing)
    assert build_chapter_markers(u, t) == ""
    assert "2" in capsys.readouterr().out  # warns, naming the count

    # headings closer than 10s apart are dropped, which can also drop below 3
    timing2 = CH_TIMING.replace("40.0\t42.0\ts2", "4.0\t6.0\ts2").replace(
        "42.0\t70.0\t3-4", "6.0\t70.0\t3-4"
    )
    u2, t2 = _write(tmp_path, timing=timing2)
    assert "\n0:04 " not in build_chapter_markers(u2, t2)


def test_chapter_markers_use_hours_past_one_hour(tmp_path):
    timing = CH_TIMING.replace("95.0\t97.0\ts3", "3700.0\t3702.0\ts3").replace(
        "97.0\t130.0\t6", "3702.0\t3800.0\t6"
    )
    u, t = _write(tmp_path, timing=timing)
    assert "1:01:40 Third section" in build_chapter_markers(u, t)


def test_manifest_entry_serialization():
    entry = ManifestEntry(
        id="Mark_Ch01",
        video_path="output/Mark_Ch01.mp4",
        thumbnail_path=None,
        book="Mark",
        chapter=1,
        language="Sindhi",
        title="Mark Chapter 01",
        description="Listen to Mark 1",
        privacy_status="unlisted",
        category_id="22",
        playlist_name="Gospel of Mark",
        tags=["Scripture", "Sindhi"],
    )
    data = entry.to_dict()
    assert data["id"] == "Mark_Ch01"
    assert data["status"] == "PENDING"

    restored = ManifestEntry.from_dict(data)
    assert restored.title == "Mark Chapter 01"
    assert restored.chapter == 1


def test_manifest_manager_save_and_load(tmp_path):
    manifest_file = tmp_path / "publish_manifest.json"
    mgr = ManifestManager(manifest_file)
    assert len(mgr.entries) == 0

    entry = ManifestEntry(
        id="Mark_Ch01",
        video_path="output/Mark_Ch01.mp4",
        thumbnail_path=None,
        book="Mark",
        chapter=1,
        language="Sindhi",
        title="Mark Chapter 01",
        description="Listen to Mark 1",
        privacy_status="unlisted",
        category_id="22",
        playlist_name="Gospel of Mark",
        tags=["Scripture", "Sindhi"],
    )
    mgr.add_or_update(entry)
    mgr.save()
    assert manifest_file.exists()

    # Reload
    mgr2 = ManifestManager(manifest_file)
    assert len(mgr2.entries) == 1
    assert mgr2.entries["Mark_Ch01"].title == "Mark Chapter 01"
    assert mgr2.get_pending_entries()[0].id == "Mark_Ch01"

    # Update status
    mgr2.update_status("Mark_Ch01", "UPLOADED", youtube_video_id="xyz123")
    mgr3 = ManifestManager(manifest_file)
    assert mgr3.entries["Mark_Ch01"].status == "UPLOADED"
    assert mgr3.entries["Mark_Ch01"].youtube_video_id == "xyz123"
    assert len(mgr3.get_pending_entries()) == 0


def test_generate_offline_package(tmp_path):
    video_file = tmp_path / "video.mp4"
    video_file.write_text("dummy video content")

    entry = ManifestEntry(
        id="Mark_Ch01",
        video_path=str(video_file),
        thumbnail_path=None,
        book="Mark",
        chapter=1,
        language="Sindhi",
        title="Mark Chapter 01",
        description="Listen to Mark 1",
        privacy_status="unlisted",
        category_id="22",
        playlist_name="Gospel of Mark",
        tags=["Scripture", "Sindhi"],
    )
    pkg_dir = generate_offline_package(entry, tmp_path)
    assert pkg_dir.exists()
    assert (pkg_dir / "metadata.txt").exists()
    assert (pkg_dir / "video.mp4").exists()

    meta_text = (pkg_dir / "metadata.txt").read_text(encoding="utf-8")
    assert "Mark Chapter 01" in meta_text
    assert "unlisted" in meta_text
