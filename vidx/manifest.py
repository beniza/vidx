"""
Publishing Manifest and Offline Package Module for VIDX
Handles metadata templating, outbox manifest generation (Option 2), and offline Studio-ready upload packages (Option 4).
"""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


class SafeDict(dict):
    """Dictionary that returns format placeholders unchanged if key is missing."""

    def __missing__(self, key):
        return f"{{{key}}}"


def resolve_metadata_template(
    template_str: str,
    book: str = "Scripture",
    chapter: int = 1,
    language: str = "",
    text_copyright: str = "",
    audio_copyright: str = "",
    **extra_kwargs,
) -> str:
    """Resolve metadata placeholders like {book}, {chapter:02d}, {language} safely."""
    if not template_str:
        return ""
    mapping = SafeDict(
        book=book,
        chapter=chapter,
        language=language,
        text_copyright=text_copyright,
        audio_copyright=audio_copyright,
        **extra_kwargs,
    )
    try:
        return template_str.format_map(mapping)
    except Exception:
        # Fallback to standard string formatting if format_map fails on complex syntax
        return template_str


@dataclass
class ManifestEntry:
    """Represents a single video item in the publishing outbox manifest."""

    id: str
    video_path: str
    thumbnail_path: Optional[str]
    book: str
    chapter: int
    language: str
    title: str
    description: str
    privacy_status: str
    category_id: str
    playlist_name: str
    tags: List[str]
    status: str = "PENDING"  # PENDING, UPLOADED, FAILED
    youtube_video_id: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManifestEntry":
        return cls(**data)


class ManifestManager:
    """Manages reading and atomically writing the publish_manifest.json outbox file."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = Path(manifest_path)
        self.entries: Dict[str, ManifestEntry] = {}
        self.load()

    def load(self):
        """Load existing manifest from disk if present."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data if isinstance(data, list) else data.get("entries", [])
                    for item in items:
                        entry = ManifestEntry.from_dict(item)
                        self.entries[entry.id] = entry
            except Exception as e:
                print(
                    f"[!] Warning: Could not load existing manifest {self.manifest_path}: {e}"
                )

    def add_or_update(self, entry: ManifestEntry):
        """Add a new entry or update an existing entry in the manifest."""
        self.entries[entry.id] = entry

    def get_pending_entries(self) -> List[ManifestEntry]:
        """Return all entries waiting to be uploaded (including previously failed attempts)."""
        return [e for e in self.entries.values() if e.status in ("PENDING", "FAILED")]

    def update_status(
        self,
        entry_id: str,
        status: str,
        youtube_video_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Update the upload status of an entry and save disk manifest immediately."""
        if entry_id in self.entries:
            entry = self.entries[entry_id]
            entry.status = status
            if youtube_video_id:
                entry.youtube_video_id = youtube_video_id
            if error_message:
                entry.error_message = error_message
            self.save()

    def save(self):
        """Atomically save the manifest to disk in formatted JSON."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.manifest_path.with_suffix(".json.tmp")
        payload = {
            "version": "1.0",
            "generator": "VIDX Scripture Video Engine",
            "entries": [e.to_dict() for e in self.entries.values()],
        }
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        temp_path.replace(self.manifest_path)


def generate_offline_package(entry: ManifestEntry, output_root: Path) -> Path:
    """
    Generate an offline 'YouTube Studio Ready' upload folder for Option 4.
    Creates text metadata ready for copy-pasting and hardlinks/references video and thumbnail.
    """
    pkg_dir = (
        output_root / "YouTube_Upload_Package" / f"{entry.book}_Ch{entry.chapter:02d}"
    )
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # Resolve absolute paths for video and thumbnail
    video_src = Path(entry.video_path)
    if not video_src.is_absolute():
        video_src = (output_root / video_src).resolve()

    video_dst = pkg_dir / video_src.name
    if video_src.exists() and not video_dst.exists():
        try:
            # Prefer hard link on Windows to save disk space
            os.link(video_src, video_dst)
        except Exception:
            try:
                shutil.copy2(video_src, video_dst)
            except Exception:
                pass

    thumb_name = "None"
    if entry.thumbnail_path:
        thumb_src = Path(entry.thumbnail_path)
        if not thumb_src.is_absolute():
            thumb_src = (output_root / thumb_src).resolve()
        thumb_dst = pkg_dir / thumb_src.name
        if thumb_src.exists() and not thumb_dst.exists():
            try:
                os.link(thumb_src, thumb_dst)
            except Exception:
                try:
                    shutil.copy2(thumb_src, thumb_dst)
                except Exception:
                    pass
        thumb_name = thumb_src.name

    # Create metadata.txt
    meta_file = pkg_dir / "metadata.txt"
    tags_str = ", ".join(entry.tags)
    content = f"""================================================================================
YOUTUBE STUDIO UPLOAD METADATA — VIDX OPTION 4 OFFLINE PACKAGE
================================================================================
VIDEO FILE:     {video_src.name}
THUMBNAIL FILE: {thumb_name}
CATEGORY ID:    {entry.category_id}
PRIVACY:        {entry.privacy_status}
PLAYLIST:       {entry.playlist_name or 'None'}

--- TITLE (Copy & Paste) ---
{entry.title}

--- DESCRIPTION (Copy & Paste) ---
{entry.description}

--- TAGS / HASHTAGS (Copy & Paste) ---
{tags_str}
================================================================================
"""
    with open(meta_file, "w", encoding="utf-8") as f:
        f.write(content)

    return pkg_dir
