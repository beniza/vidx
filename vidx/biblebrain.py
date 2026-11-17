"""
Bible Brain (DBP v4) import for VIDX.

Pulls USFM-ready text, chapter audio and (optionally) verse timing from Bible
Brain so a team can render a Scripture video without a Scripture App Builder
project. Standard library only; the API key is never written to disk.

Endpoint paths and response field names live in BibleBrainClient so they can be
corrected in one place against https://4.dbt.io/open-api-4.json.
"""

import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import yaml

BASE_URL = "https://4.dbt.io/api"
TEXT_TYPES = ("text_plain",)  # USX filesets could be added once converted to USFM
AUDIO_TYPES = ("audio", "audio_drama")  # downloadable MP3; HLS "_stream" types excluded


class BibleBrainError(RuntimeError):
    pass


class NoChapterError(BibleBrainError):
    """The chapter has no text or audio: the end of the book, when importing a whole book."""


@dataclass
class Fileset:
    id: str
    type: str
    size: str = ""

    @property
    def is_text(self):
        return self.type in TEXT_TYPES

    @property
    def is_audio(self):
        return self.type in AUDIO_TYPES


@dataclass
class BibleOption:
    bible_id: str
    name: str
    language: str = ""
    text: list = field(default_factory=list)
    audio: list = field(default_factory=list)


class BibleBrainClient:
    def __init__(self, api_key=None, timeout=30, pause=0.2, opener=None):
        self.api_key = api_key or os.environ.get("BIBLE_BRAIN_KEY", "")
        if not self.api_key:
            raise BibleBrainError("No API key. Enter one or set BIBLE_BRAIN_KEY.")
        self.timeout = timeout
        self.pause = pause
        self._open = opener or urllib.request.urlopen

    def _get(self, path, **params):
        params = {k: v for k, v in params.items() if v is not None}
        params.update({"key": self.api_key, "v": 4})
        url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "vidx"})
        try:
            with self._open(req, timeout=self.timeout) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise BibleBrainError("API key rejected by Bible Brain.") from e
            raise BibleBrainError(f"Bible Brain returned HTTP {e.code} for {path}") from e
        except urllib.error.URLError as e:
            raise BibleBrainError(f"Network problem: {e.reason}") from e
        time.sleep(self.pause)
        return body

    def _paged(self, path, **params):
        page, out = 1, []
        while True:
            body = self._get(path, page=page, limit=100, **params)
            out.extend(body.get("data", []))
            pg = (body.get("meta") or {}).get("pagination") or {}
            last = pg.get("total_pages") or pg.get("last_page") or 1
            if page >= last:
                return out
            page += 1

    # ---- discovery -------------------------------------------------------
    def countries(self):
        return sorted(self._paged("/countries"), key=lambda c: c.get("name", ""))

    def languages(self, country_code):
        return sorted(self._paged("/languages", country=country_code), key=lambda x: x.get("name", ""))

    def bibles(self, language_code):
        return self._paged("/bibles", language_code=language_code)

    def bible(self, bible_id):
        """One Bible by id (e.g. MALMAL), or None when Bible Brain does not know it."""
        try:
            data = self._get(f"/bibles/{bible_id}").get("data")
        except BibleBrainError as e:
            if "HTTP 404" in str(e):
                return None
            raise
        if isinstance(data, list):
            data = data[0] if data else None
        return data or None

    # ---- content ---------------------------------------------------------
    def fileset_files(self, fileset_id):
        """Whole-fileset listing: data[].path are signed URLs (as used by BB Drain)."""
        return self._get(f"/bibles/filesets/{fileset_id}").get("data", [])

    def chapter_text(self, fileset_id, book, chapter):
        data = self._get(f"/bibles/filesets/{fileset_id}/{book}/{chapter}").get("data", [])
        return [(str(v.get("verse_start")), (v.get("verse_text") or "").strip()) for v in data]

    def chapter_audio(self, fileset_id, book, chapter):
        """Returns (signed_url, duration_seconds or None)."""
        try:
            data = self._get(f"/bibles/filesets/{fileset_id}/{book}/{chapter}").get("data", [])
        except BibleBrainError:
            data = []
        if not data:
            data = [f for f in self.fileset_files(fileset_id)
                    if f.get("book_id") == book and int(f.get("chapter_start") or 0) == chapter]
        if not data:
            raise NoChapterError(f"No audio for {book} {chapter} in {fileset_id}")
        return data[0].get("path"), data[0].get("duration")

    def timestamps(self, fileset_id, book, chapter):
        """[(verse_start, verse_end, start_seconds)], or [] when no timing exists."""
        try:
            data = self._get(f"/timestamps/{fileset_id}/{book}/{chapter}").get("data", [])
        except BibleBrainError:
            return []
        return [(str(t.get("verse_start")), t.get("verse_end"), float(t.get("timestamp"))) for t in data]

    def download(self, url, dest):
        # Signed CDN URLs expire: download immediately after requesting them.
        req = urllib.request.Request(url, headers={"User-Agent": "vidx"})
        with self._open(req, timeout=self.timeout) as r, open(dest, "wb") as f:
            while chunk := r.read(1 << 16):
                f.write(chunk)


# ---- discovery cache -----------------------------------------------------
def default_cache_path():
    return Path(os.environ.get("VIDX_BB_CACHE") or Path.home() / ".vidx" / "biblebrain-cache.json")


class CachedClient:
    """Caches country, language and Bible lists on disk (7 days by default).

    These lookups rarely change but cost one API call per language, so a country
    scan takes minutes cold and no time warm. Only discovery data is cached: never the
    API key, signed URLs, text or audio. refresh=True re-fetches each list once and
    updates the cache. Everything else is passed straight to the wrapped client.
    """

    CACHED = ("countries", "languages", "bibles")

    def __init__(self, inner, path=None, ttl=7 * 86400, refresh=False):
        self._inner = inner
        self.path = Path(path) if path else default_cache_path()
        self.ttl = ttl
        self.refresh = refresh
        self._lock = threading.Lock()
        self._fetched = set()
        self._data = self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass  # the cache is best-effort

    def _cached(self, key, fetch):
        with self._lock:
            hit = self._data.get(key)
            fresh = hit and (time.time() - hit.get("t", 0)) <= self.ttl
            if fresh and (not self.refresh or key in self._fetched):
                return hit["v"]
        value = fetch()
        with self._lock:
            self._data[key] = {"t": time.time(), "v": value}
            self._fetched.add(key)
            self._save()
        return value

    def countries(self):
        return self._cached("countries", self._inner.countries)

    def languages(self, country_code):
        return self._cached(f"languages:{country_code}", lambda: self._inner.languages(country_code))

    def bibles(self, language_code):
        return self._cached(f"bibles:{language_code}", lambda: self._inner.bibles(language_code))

    def __getattr__(self, name):  # chapter_text, chapter_audio, timestamps, download, bible, ...
        return getattr(self._inner, name)


# ---- pure helpers --------------------------------------------------------
def country_code(country):
    codes = country.get("codes") or {}
    return codes.get("iso_a2") or country.get("country_id") or country.get("iso_a2") or country.get("code")


def collect_filesets(bible):
    raw = bible.get("filesets") or {}
    groups = raw.values() if isinstance(raw, dict) else [raw]
    out = []
    for g in groups:
        for fs in g if isinstance(g, list) else []:
            out.append(Fileset(id=fs.get("id", ""), type=fs.get("type", ""), size=fs.get("size", "")))
    return out


def eligible_bibles(raw_bibles, language_name=""):
    """Keep only Bibles that have BOTH a text and a downloadable audio fileset."""
    result = []
    for b in raw_bibles:
        fs = collect_filesets(b)
        text = [f for f in fs if f.is_text]
        audio = [f for f in fs if f.is_audio]
        if text and audio:
            result.append(BibleOption(
                bible_id=b.get("abbr") or b.get("id", ""),
                name=b.get("name") or b.get("vname") or b.get("abbr", ""),
                language=language_name, text=text, audio=audio))
    return result


def parse_chapters(spec):
    """'1-3,5' -> [1, 2, 3, 5]; 'all' -> None (every chapter until the book ends)."""
    spec = (spec or "").strip().lower()
    if spec == "all":
        return None
    out = []
    for part in spec.split(","):
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part.strip())
        if not m:
            raise ValueError(f"Bad chapter list {spec!r}: use e.g. 1-5, 1,3,5 or all")
        a = int(m.group(1))
        b = int(m.group(2) or a)
        if a < 1 or b < a:
            raise ValueError(f"Bad chapter range {part!r}")
        out.extend(n for n in range(a, b + 1) if n not in out)
    return out


def to_usfm(book, chapter, verses, title=""):
    lines = [f"\\id {book} {title}".rstrip(), f"\\c {chapter}"]
    lines += [f"\\v {num} {text}" for num, text in verses if text]
    return "\n".join(lines) + "\n"


def stamps_to_rows(stamps, total):
    """Bible Brain gives start times only: each end is the next start, the last is the audio length.

    Verse 0 (chapter intro) is dropped: its audio is absorbed by the first verse row.
    """
    usable = [s for s in stamps if str(s[0]) != "0"]
    usable.sort(key=lambda s: s[2])
    rows = []
    for i, (vs, ve, start) in enumerate(usable):
        label = str(vs) if not ve or str(ve) == str(vs) else f"{vs}-{ve}"
        end = usable[i + 1][2] if i + 1 < len(usable) else total
        rows.append((start, end, label))
    return rows


def _duration(path, hint):
    if hint:
        return float(hint)
    if shutil.which("ffprobe"):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        return float(out.stdout.strip())
    raise BibleBrainError("Audio duration unknown and ffprobe was not found.")


def probe_timing(client, opt, book, chapter):
    """True if any audio fileset has verse timing for this chapter (checked on one chapter)."""
    return any(client.timestamps(a.id, book, chapter) for a in opt.audio)


def import_chapter(client, opt, book, chapter, out_dir, timing_source, total_hint=None):
    """Download one chapter into out_dir. timing_source: 'biblebrain' or 'vidx'.

    Names follow VIDX invariants: audio starts with the chapter number (chapter
    inference takes the FIRST number in the stem and book codes like 1CO start with a
    digit); timing uses the BOOK-NN-timing.txt name that --align writes.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{book}-{chapter:02d}"
    usfm = out_dir / f"{stem}.usfm"
    audio = out_dir / f"{chapter:02d}_{book}.mp3"
    timing = out_dir / f"{stem}-timing.txt"

    verses = client.chapter_text(opt.text[0].id, book, chapter)
    if not verses:
        raise NoChapterError(f"No text for {book} {chapter} in {opt.text[0].id}")
    usfm.write_text(to_usfm(book, chapter, verses, opt.name), encoding="utf-8")

    url, dur = client.chapter_audio(opt.audio[0].id, book, chapter)
    client.download(url, str(audio))

    if timing_source == "biblebrain":
        from .align import write_timing_file
        rows = stamps_to_rows(client.timestamps(opt.audio[0].id, book, chapter),
                              _duration(audio, total_hint or dur))
        if not rows:
            raise BibleBrainError(f"No Bible Brain timing for {book} {chapter}.")
        write_timing_file(timing, rows, book=book, chapter=chapter, level="verse")
    return {"usfm": usfm, "audio": audio, "timing": timing, "name": stem}


def jobs_yaml(imports, video_dir):
    jobs = [{"usfm": str(i["usfm"]), "timing": str(i["timing"]), "audio": str(i["audio"]),
             "output": str(Path(video_dir) / f"{i['name']}.mp4")} for i in imports]
    return yaml.safe_dump({"project": {"output_dir": str(video_dir)}, "jobs": jobs},
                          sort_keys=False, allow_unicode=True)


def import_book(client, opt, book, chapters, out_dir, source, say=print, max_chapters=150):
    """Import chapters; returns (imports, failures).

    chapters=None means the whole book: go on until a chapter has no text or audio.
    That is the end of the book, not a failure. Other problems (no timing for one
    chapter, a dropped connection) are reported per chapter and the run continues.
    """
    imports, failures = [], []
    for ch in (chapters if chapters is not None else range(1, max_chapters + 1)):
        try:
            imports.append(import_chapter(client, opt, book, ch, out_dir, source))
            say(f"  imported {book} {ch}")
        except NoChapterError as e:
            if chapters is None:
                if not imports:
                    raise BibleBrainError(f"No chapters found for {book}: {e}") from e
                break
            failures.append((ch, str(e)))
            say(f"  skipped {book} {ch}: {e}")
        except BibleBrainError as e:
            failures.append((ch, str(e)))
            say(f"  skipped {book} {ch}: {e}")
    return imports, failures


def _finish(imports, source, out_dir, book, say):
    jobs = Path(out_dir) / "bb_jobs.yaml"
    jobs.write_text(jobs_yaml(imports, Path(out_dir) / "video"), encoding="utf-8")
    say(f"\nDone. Render with:  vidx -c {jobs} --bg <background.mp4>")
    if source == "vidx":
        say("Timing files do not exist yet. Create each with:")
        for i in imports:
            m = re.search(r"-(\d+)$", i["name"])
            say(f"  vidx --align --usfm {i['usfm']} --audio {i['audio']} --book {book} --chapter {int(m.group(1))}")
    return jobs


def run_biblebrain_batch(client, out_dir, bible_id, language, book, chapters, timing="auto", say=print):
    """Scripted import of one book: no prompts. Returns (jobs_path, failures)."""
    if language:
        raw = [b for b in client.bibles(language) if (b.get("abbr") or b.get("id")) == bible_id]
    else:
        found = client.bible(bible_id)
        raw = [found] if found else []
    if not raw:
        raise BibleBrainError(f"Bible {bible_id} was not found" + (f" for language {language}." if language else "."))
    opts = eligible_bibles(raw)
    if not opts:
        raise BibleBrainError(f"{bible_id} does not have both text and downloadable audio.")
    opt = opts[0]

    book = book.strip().upper()
    if timing == "auto":
        timing = "biblebrain" if probe_timing(client, opt, book, (chapters or [1])[0]) else "vidx"
        say(f"Timing source: {'Bible Brain' if timing == 'biblebrain' else 'VIDX (none in Bible Brain)'}")
    root = Path(out_dir) / "src" / opt.bible_id
    imports, failures = import_book(client, opt, book, chapters, root, timing, say)
    if not imports:
        raise BibleBrainError("Nothing was imported.")
    return _finish(imports, timing, out_dir, book, say), failures


# ---- interactive wizard --------------------------------------------------
def _pick(label, items, ask, say):
    for n, it in enumerate(items, 1):
        say(f"  {n:>3}. {it}")
    while True:
        s = ask(f"{label} (number, or part of a name): ").strip()
        if s.isdigit() and 1 <= int(s) <= len(items):
            return int(s) - 1
        hits = [i for i, it in enumerate(items) if s and s.lower() in it.lower()]
        if len(hits) == 1:
            return hits[0]
        say("  Narrowed to: " + (", ".join(items[i] for i in hits[:8]) or "nothing, try again"))


def run_biblebrain(client, out_dir, ask=None, say=print, timing_choice=None):
    """Key is already in `client`. Country -> language -> Bible -> chapters -> files + jobs YAML."""
    ask = ask or input  # resolved at call time so tests and callers can swap input()
    out_dir = Path(out_dir)
    countries = client.countries()
    c = countries[_pick("Country", [x.get("name", "") for x in countries], ask, say)]
    langs = client.languages(country_code(c))

    say(f"Checking text + audio availability for {len(langs)} languages in {c.get('name')}...")

    def check(lg):
        return lg.get("name", ""), eligible_bibles(client.bibles(lg.get("iso") or lg.get("code")), lg.get("name", ""))

    with ThreadPoolExecutor(max_workers=4) as pool:
        usable = [(n, o) for n, o in pool.map(check, langs) if o]
    if not usable:
        say("No language in this country has a Bible with both text and audio.")
        return None

    name, opts = usable[_pick("Language", [u[0] for u in usable], ask, say)]
    opt = opts[_pick("Bible", [f"{o.name} [{o.bible_id}]" for o in opts], ask, say)]

    book = ask("Book code (USFM, e.g. MRK, 1CO): ").strip().upper()
    first = ask("First chapter (or 'all' for the whole book): ").strip()
    chapters = None if first.lower() == "all" else list(range(int(first), int(ask("Last chapter (Enter = same): ") or first) + 1))

    source = timing_choice or "vidx"
    probe_ch = (chapters or [1])[0]
    if timing_choice in (None, "auto") and probe_timing(client, opt, book, probe_ch):
        if timing_choice == "auto":
            source = "biblebrain"
        else:
            source = "biblebrain" if ask("Verse timing is available from Bible Brain. Use it? [Y/n]: ").lower() != "n" else "vidx"
    elif timing_choice in (None, "auto"):
        say("No Bible Brain timing for this Bible: VIDX timing (SAB file or --align) will be used.")
        source = "vidx"

    imports, failures = import_book(client, opt, book, chapters, out_dir / "src" / opt.bible_id, source, say)
    if not imports:
        say("Nothing was imported.")
        return None
    jobs = _finish(imports, source, out_dir, book, say)
    for ch, why in failures:
        say(f"  not imported: {book} {ch} ({why})")
    return jobs
