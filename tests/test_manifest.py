from vidx.manifest import (
    resolve_metadata_template,
    ManifestEntry,
    ManifestManager,
    generate_offline_package,
)


def test_resolve_metadata_template():
    tmpl = "{book} Chapter {chapter:02d} — {language}"
    res = resolve_metadata_template(tmpl, book="Mark", chapter=3, language="Sindhi")
    assert res == "Mark Chapter 03 — Sindhi"

    # Missing key fallback
    tmpl_missing = "{book} Chapter {chapter} by {author}"
    res_missing = resolve_metadata_template(tmpl_missing, book="John", chapter=1)
    assert res_missing == "John Chapter 1 by {author}"


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
