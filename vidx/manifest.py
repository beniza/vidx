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

from .usfm_parser import USFMParser, TimingParser, parse_segment_id

# YouTube ignores the whole chapter list unless it starts at 0:00, has at least
# three markers, and every chapter runs 10s or more.
YT_MIN_MARKERS = 3
YT_MIN_CHAPTER_SEC = 10.0


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


def _read(path):
    # utf-8-sig: a BOM'd \id line otherwise fails every marker regex (cli.py does the same)
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def usfm_book_name(usfm_file) -> str:
    """The book's own name from \\h, e.g. 'മർക്കോച്ച്'. Empty if absent.

    `{book}` is the \\id code (MRK); this is what a reader would recognise.
    """
    for line in _read(usfm_file).split("\n"):
        if line.startswith("\\h "):
            return line[3:].strip()
    return ""


def _timestamp(seconds: float) -> str:
    """YouTube chapter timestamp: M:SS, or H:MM:SS past the hour."""
    total = int(seconds)  # floor, so a marker never rounds past its own boundary
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_chapter_markers(
    usfm_file,
    timing_file,
    chapter=None,
    offset_seconds: float = 0.0,
    intro_label: str = "Introduction",
) -> str:
    """Build a YouTube chapter block from the \\s headings and their timings.

    Returns lines like ``0:00 Heading (1:1-8)``, or "" (with a printed warning)
    when the data cannot satisfy YouTube's rules -- a chapter with two headings
    is ordinary translation data, not a misconfiguration, so this never raises.
    """
    tp = TimingParser(_read(timing_file), filepath=str(timing_file))
    tp.shift_timestamps(offset_seconds)  # keep bumper intros in step
    if not tp.entries:
        return ""

    # Prefer the timing file's own \c: the single-job CLI path may not know the
    # chapter, and batch_runner falls back to 1, which would caption a video
    # with some other chapter's headings.
    up = USFMParser(_read(usfm_file), target_chapter=str(tp.chapter or chapter or 1))

    # Walk the rows once, pairing each heading with the verses that follow it.
    rows = []  # [start, heading_text, [verse ids...]]
    for e in tp.entries:
        vid, marker = parse_segment_id(e["segment"])
        if vid == "section":
            text = up.get_section_heading(marker)
            if text:
                rows.append([float(e["start"]), text, []])
        elif vid and rows and vid not in rows[-1][2]:
            rows[-1][2].append(vid)
    if not rows:
        return ""

    if rows[0][0] < YT_MIN_CHAPTER_SEC:
        rows[0][0] = 0.0                       # first heading owns 0:00
    else:
        rows.insert(0, [0.0, intro_label, []])  # verse 1 precedes the heading

    chap = up.chapter or tp.chapter or ""
    end = float(tp.entries[-1]["end"])

    kept = []
    for start, text, verses in rows:
        # One rule enforces the 10s minimum, strict ascending order, and (since
        # timestamps are floored to whole seconds) no two identical labels.
        if kept and start < kept[-1][0] + YT_MIN_CHAPTER_SEC:
            continue
        label = text
        if verses:
            # Endpoints, not raw ids: a merged verse is itself "3-4", so joining
            # ids would read "3-4-5" for a section spanning 3-4 through 5.
            first = verses[0].split("-")[0]
            last = verses[-1].split("-")[-1]
            span = first if first == last else f"{first}-{last}"
            label = f"{text} ({chap}:{span})" if chap else f"{text} ({span})"
        kept.append((start, label))
    # the final chapter must also run 10s or more
    if len(kept) > 1 and end - kept[-1][0] < YT_MIN_CHAPTER_SEC:
        kept.pop()

    if len(kept) < YT_MIN_MARKERS:
        print(
            f"[!] Chapter markers skipped for {Path(timing_file).name}: only "
            f"{len(kept)} usable section heading(s); YouTube needs {YT_MIN_MARKERS}."
        )
        return ""
    return "\n".join(f"{_timestamp(s)} {label}" for s, label in kept)


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
