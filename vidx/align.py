"""
Forced alignment: generate SAB-style timing files from audio + USFM text.

Uses Meta's MMS-300M-1130 forced aligner (Wav2Vec2 CTC, 1130+ languages) via
ONNX Runtime, so no PyTorch dependency. Text is romanized with uroman, which
makes the whole thing script-agnostic -- Malayalam, Sindhi, Devanagari, Arabic
all reduce to the same 26-letter CTC vocabulary.

Optional extra: pip install vidx[align]
"""

import json
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import numpy as np
    import onnxruntime as ort
    import uroman as _uroman

    ALIGN_AVAILABLE = True
    _ALIGN_IMPORT_ERROR = None
except ImportError as e:  # pragma: no cover - exercised only without the extra
    ALIGN_AVAILABLE = False
    _ALIGN_IMPORT_ERROR = e

SAMPLE_RATE = 16_000
SAMPLES_PER_FRAME = 320  # product of conv_stride -> 20ms per frame
SEC_PER_FRAME = SAMPLES_PER_FRAME / SAMPLE_RATE

# Inference is chunked because wav2vec2 self-attention is O(T^2): a 7-minute
# chapter in one pass would need a ~20k x 20k attention matrix.
CHUNK_SEC = 20.0
CONTEXT_SEC = 2.0

_HF_REPO = "romara-labs/mms-300m-1130-forced-aligner-ONNX"
_MODEL_FILES = ("model.q8.onnx", "vocab.json")


def default_model_dir() -> Path:
    return Path.home() / ".vidx" / "mms-aligner"


def ensure_model(model_dir: Optional[Path] = None, quiet: bool = False) -> Path:
    """Download the ONNX aligner on first use (~340MB, cached under ~/.vidx)."""
    model_dir = Path(model_dir) if model_dir else default_model_dir()
    model_dir.mkdir(parents=True, exist_ok=True)
    for name in _MODEL_FILES:
        target = model_dir / name
        if target.exists() and target.stat().st_size > 0:
            continue
        url = f"https://huggingface.co/{_HF_REPO}/resolve/main/{name}"
        if not quiet:
            print(f"[*] Downloading aligner model: {name} (first run only)")
        tmp = target.with_suffix(target.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(target)
    return model_dir


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


def load_audio(path, start_sec: float = 0.0, end_sec: Optional[float] = None):
    """Decode any ffmpeg-readable file to normalized 16kHz mono float32."""
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if start_sec:
        cmd += ["-ss", str(start_sec)]
    cmd += ["-i", str(path)]
    if end_sec is not None:
        cmd += ["-t", str(end_sec - start_sec)]
    cmd += ["-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32).copy()
    # zero-mean / unit-variance over the whole utterance (preprocessor default)
    return (audio - audio.mean()) / (audio.std() + 1e-7)


def audio_duration(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


# ---------------------------------------------------------------------------
# Text -> CTC targets
# ---------------------------------------------------------------------------


@dataclass
class Segment:
    """One unit to be timed (a verse, a heading, or a phrase within a verse)."""

    seg_id: str
    text: str


class Romanizer:
    """uroman wrapper; caching matters because whole books repeat vocabulary."""

    def __init__(self, lang: Optional[str] = None):
        self._u = _uroman.Uroman()
        self._lang = lang
        self._cache = {}

    def __call__(self, text: str) -> str:
        key = text
        hit = self._cache.get(key)
        if hit is None:
            hit = self._u.romanize_string(text, lcode=self._lang)
            self._cache[key] = hit
        return hit


def build_targets(segments, vocab, romanizer):
    """Flatten segments into one CTC target sequence.

    Returns (targets, seg_char_starts) where seg_char_starts[i] is the index
    into `targets` at which segment i begins. Word boundaries need no explicit
    token: the MMS vocabulary is letters only and CTC blanks absorb the pauses.
    """
    targets, seg_char_starts, kept = [], [], []
    for seg in segments:
        roman = romanizer(seg.text).lower()
        ids = [vocab[ch] for ch in roman if ch in vocab and ch not in ("<blank>",)]
        if not ids:
            continue
        seg_char_starts.append(len(targets))
        targets.extend(ids)
        kept.append(seg)
    return targets, seg_char_starts, kept


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------


def _log_softmax(x):
    m = x.max(axis=-1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=-1, keepdims=True))


def compute_log_probs(session, audio, progress=None):
    """Run the model over the audio in overlapping chunks, keeping chunk centres."""
    chunk = int(CHUNK_SEC * SAMPLE_RATE)
    ctx = int(CONTEXT_SEC * SAMPLE_RATE)
    out = []
    n_chunks = max(1, -(-len(audio) // chunk))
    for i in range(n_chunks):
        beg, end = i * chunk, min((i + 1) * chunk, len(audio))
        lo, hi = max(0, beg - ctx), min(len(audio), end + ctx)
        window = audio[lo:hi]
        if len(window) < SAMPLES_PER_FRAME * 2:
            continue
        logits = session.run(
            ["logits"],
            {
                "input_values": window[None, :].astype(np.float32),
                "attention_mask": np.ones((1, len(window)), dtype=np.int64),
            },
        )[0][0]
        # trim the context frames we added so chunks concatenate seamlessly
        lead = (beg - lo) // SAMPLES_PER_FRAME
        keep = (end - beg) // SAMPLES_PER_FRAME
        out.append(logits[lead:lead + keep])
        if progress:
            progress(i + 1, n_chunks)
    return _log_softmax(np.concatenate(out, axis=0).astype(np.float32))


# ---------------------------------------------------------------------------
# Vectorized CTC Viterbi
# ---------------------------------------------------------------------------


def forced_align(log_probs, targets, blank_id=0):
    """Viterbi over the CTC lattice.

    Returns (first_frame, last_frame) per target character.

    Vectorized across states -- the reference implementation loops in Python and
    needs ~200M iterations for one chapter, which takes hours.

    ponytail: backpointers are uint8 [T, 2K+1] (~330MB for a 7-min chapter).
    Fine per chapter; chunk with anchors if whole-book single-pass is ever needed.
    """
    T = log_probs.shape[0]
    K = len(targets)
    S = 2 * K + 1
    if T < K:
        raise ValueError(f"Audio too short: {T} frames for {K} target characters.")

    tgt = np.asarray(targets, dtype=np.int64)
    states = np.full(S, blank_id, dtype=np.int64)
    states[1::2] = tgt

    # a skip (s-2 -> s) is legal only into a non-blank differing from states[s-2]
    allowed2 = np.zeros(S, dtype=bool)
    allowed2[3::2] = tgt[1:] != tgt[:-1]

    NEG = np.float32(-1e30)
    prev = np.full(S, NEG, dtype=np.float32)
    prev[0] = log_probs[0, blank_id]
    if S > 1:
        prev[1] = log_probs[0, states[1]]

    bp = np.zeros((T, S), dtype=np.uint8)
    cand = np.empty((3, S), dtype=np.float32)

    for t in range(1, T):
        cand[0] = prev
        cand[1, 0] = NEG
        cand[1, 1:] = prev[:-1]
        cand[2, :2] = NEG
        cand[2, 2:] = np.where(allowed2[2:], prev[:-2], NEG)
        choice = cand.argmax(axis=0)
        prev = cand[choice, np.arange(S)] + log_probs[t, states]
        bp[t] = choice

    # terminal state: last token or the trailing blank
    s = S - 1 if S == 1 or prev[S - 1] >= prev[S - 2] else S - 2

    state_path = np.empty(T, dtype=np.int32)
    for t in range(T - 1, 0, -1):
        state_path[t] = s
        s -= int(bp[t, s])
    state_path[0] = s

    # token k occupies state 2k+1; record the frame span it holds
    first_frame = np.zeros(K, dtype=np.int64)
    last_frame = np.zeros(K, dtype=np.int64)
    odd = state_path % 2 == 1
    idx = (state_path[odd] - 1) // 2
    frames = np.nonzero(odd)[0]
    # np.minimum/maximum.at give per-token first and last occupied frame
    first_frame.fill(T)
    np.minimum.at(first_frame, idx, frames)
    np.maximum.at(last_frame, idx, frames)
    return first_frame, last_frame


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def align_segments(audio_path, segments, lang=None, model_dir=None,
                   start_sec=0.0, end_sec=None, progress=None):
    """Align `segments` against `audio_path`. Returns [(start, end, seg_id), ...]."""
    if not ALIGN_AVAILABLE:
        raise RuntimeError(
            f"Alignment dependencies missing ({_ALIGN_IMPORT_ERROR}). "
            "Run: pip install vidx[align]"
        )
    model_dir = ensure_model(model_dir)
    vocab = json.loads((model_dir / "vocab.json").read_text(encoding="utf-8"))
    blank_id = vocab["<blank>"]

    targets, seg_starts, kept = build_targets(segments, vocab, Romanizer(lang))
    if not targets:
        raise ValueError("No alignable text after romanization.")

    audio = load_audio(audio_path, start_sec, end_sec)
    session = ort.InferenceSession(
        str(model_dir / "model.q8.onnx"), providers=["CPUExecutionProvider"]
    )
    log_probs = compute_log_probs(session, audio, progress)
    first_frame, last_frame = forced_align(log_probs, targets, blank_id)

    # CTC fires late -- a character's peak sits inside the word, not at its onset.
    # Put each boundary in the middle of the silence before the segment's first
    # character instead, which is where a human (and aeneas) would cut.
    def boundary(char_idx):
        f = first_frame[char_idx]
        if char_idx == 0:
            return f
        gap_start = last_frame[char_idx - 1] + 1
        return (gap_start + f) / 2.0 if f > gap_start else f

    starts = [start_sec + boundary(i) * SEC_PER_FRAME for i in seg_starts]
    span_end = start_sec + log_probs.shape[0] * SEC_PER_FRAME
    ends = starts[1:] + [end_sec if end_sec is not None else span_end]
    return [
        (round(s, 3), round(e, 3), seg.seg_id)
        for s, e, seg in zip(starts, ends, kept)
    ]


DEFAULT_SEPARATORS = [".", "?", "؟", "!", ",", "،", ";", "؛", ":", "।"]


def _heading_before_verse(parser):
    """Map verse number -> section heading text that precedes it, in file order.

    parser.sections is keyed by marker and loses both position and duplicates,
    so walk the raw USFM instead. Narrators normally read these titles aloud,
    and SAB timing files list them as s1/s2/... -- omitting them makes the
    following verse absorb the heading audio.
    """
    headings, pending, in_chapter = {}, [], parser.target_chapter is None
    for line in parser.content.split("\n"):
        line = line.strip()
        m = re.match(r"\\c\s+(\S+)", line)
        if m:
            if parser.target_chapter is not None:
                was = in_chapter
                in_chapter = str(m.group(1)).strip() == str(parser.target_chapter).strip()
                if was and not in_chapter:
                    break
            pending = []
            continue
        if not in_chapter:
            continue
        if re.match(r"\\s\d*\s", line):  # \s, \s1, \s2 -- but not \r or \sp
            text = parser._clean_text(line)
            if text:
                pending.append(text)
        elif re.match(r"\\v\s+(\S+)", line):
            if pending:
                headings[re.match(r"\\v\s+(\S+)", line).group(1)] = pending
                pending = []
    return headings


def segments_from_usfm(parser, level="verse", separators=None, headings=True):
    """Build the ordered list of units to time from a parsed USFM chapter."""
    seps = separators or DEFAULT_SEPARATORS
    before = _heading_before_verse(parser) if headings else {}
    out, h_index = [], 0
    for vnum, text in parser.verses.items():
        text = (text or "").strip()
        if not text:
            continue
        for htext in before.get(str(vnum), []):
            h_index += 1
            out.append(Segment(f"s{h_index}", htext))
        if level != "phrase":
            out.append(Segment(str(vnum), text))
            continue
        parts, cur = [], ""
        for ch in text:
            cur += ch
            if ch in seps:
                if cur.strip():
                    parts.append(cur.strip())
                cur = ""
        if cur.strip():
            parts.append(cur.strip())
        if len(parts) <= 1:
            out.append(Segment(str(vnum), text))
        else:
            for i, p in enumerate(parts):
                out.append(Segment(f"{vnum}{chr(ord('a') + i)}", p))
    return out


def to_audacity_labels(rows) -> str:
    """A SAB timing body *is* an Audacity label track -- just drop the header."""
    return "".join(f"{s:.6f}\t{e:.6f}\t{sid}\n" for s, e, sid in rows)


def from_audacity_labels(text):
    """Read back an exported Audacity label track."""
    rows = []
    for line in text.splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 3:
            try:
                rows.append((float(parts[0]), float(parts[1]), parts[2]))
            except ValueError:
                continue
    return rows


def write_timing_file(path, rows, book, chapter, level="verse", separators=None):
    """Emit a SAB-compatible timing file."""
    lines = [f"\\id {book}", f"\\c {chapter}", f"\\level {level}"]
    if separators:
        lines.append("\\separators " + " ".join(separators))
    lines += [f"{s:.3f}\t{e:.3f}\t{sid}" for s, e, sid in rows]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
