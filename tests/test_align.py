"""Checks for forced alignment that don't need the 356MB model download."""

import pytest

np = pytest.importorskip("numpy", reason="requires the optional 'align' extra")

from vidx.align import (
    SEC_PER_FRAME,
    Segment,
    _rows_from_frames,
    forced_align,
    from_audacity_labels,
    segments_from_usfm,
    to_audacity_labels,
)

BLANK = 0
A, B = 1, 2


def _log_probs(frames, vocab=3, peak=0.0, floor=-20.0):
    """Build [T, V] log-probs where `frames[t]` is the near-certain token."""
    lp = np.full((len(frames), vocab), floor, dtype=np.float32)
    for t, tok in enumerate(frames):
        lp[t, tok] = peak
    return lp


def test_viterbi_recovers_obvious_alignment():
    # blank a a blank b blank  ->  'a' spans frames 1-2, 'b' is frame 4
    lp = _log_probs([BLANK, A, A, BLANK, B, BLANK])
    first, last = forced_align(lp, [A, B], blank_id=BLANK)
    assert list(first) == [1, 4]
    assert list(last) == [2, 4]


def test_viterbi_handles_repeated_token():
    # 'aa' must be separated by a blank, so the second 'a' cannot start before it
    lp = _log_probs([A, BLANK, A, A])
    first, last = forced_align(lp, [A, A], blank_id=BLANK)
    assert list(first) == [0, 2]
    assert list(last) == [0, 3]


def test_viterbi_is_monotonic_and_covers_every_target():
    rng = np.random.default_rng(0)
    targets = [1 + (i % 2) for i in range(12)]
    lp = rng.normal(size=(200, 3)).astype(np.float32)
    first, last = forced_align(lp, targets, blank_id=BLANK)
    assert len(first) == len(targets)
    assert all(first[i] <= last[i] for i in range(len(targets)))
    # each target starts no earlier than the previous one ended
    assert all(first[i] > last[i - 1] for i in range(1, len(targets)))


def test_viterbi_rejects_audio_shorter_than_text():
    lp = _log_probs([A, B])
    with pytest.raises(ValueError):
        forced_align(lp, [A, B, A, B, A], blank_id=BLANK)


def test_rows_end_at_last_speech_frame_not_end_of_audio():
    # Two segments. Speech stops at frame 5; the audio itself may run far longer,
    # and _rows_from_frames must not know or care -- it only sees the frames.
    first = np.array([0, 4])
    last = np.array([1, 5])
    segs = [Segment("1", "a"), Segment("2", "b")]
    rows = _rows_from_frames(first, last, [0, 1], segs)
    assert rows[-1][1] == pytest.approx(6 * SEC_PER_FRAME)
    assert rows[0][1] == rows[1][0]  # contiguous, no gap


def test_boundary_leads_the_pause_midpoint():
    # Pause runs from frame 2 (first silent) to frame 60 (next verse's onset), so
    # the midpoint is 31 and the 0.15s (7.5-frame) lead pulls the cut back to 23.5.
    first = np.array([0, 60])
    last = np.array([1, 61])
    segs = [Segment("1", "a"), Segment("2", "b")]
    rows = _rows_from_frames(first, last, [0, 1], segs)
    assert rows[1][0] == pytest.approx(23.5 * SEC_PER_FRAME)


def test_short_pause_never_backs_into_the_previous_verse():
    # Pause is only 2 frames (0.04s), far shorter than the lead. The boundary must
    # clamp to the first silent frame rather than landing inside verse 1's audio.
    first = np.array([0, 4])
    last = np.array([1, 5])
    segs = [Segment("1", "a"), Segment("2", "b")]
    rows = _rows_from_frames(first, last, [0, 1], segs)
    assert rows[1][0] == pytest.approx(2 * SEC_PER_FRAME)
    assert rows[1][0] > last[0] * SEC_PER_FRAME  # after verse 1's last frame


def test_audacity_round_trip_preserves_rows():
    rows = [(0.0, 1.5, "1"), (1.5, 3.25, "2a"), (3.25, 9.0, "2b")]
    back = from_audacity_labels(to_audacity_labels(rows))
    assert back == rows


class _FakeParser:
    def __init__(self, verses, content="", target_chapter=None):
        self.verses = verses
        self.content = content
        self.target_chapter = target_chapter

    @staticmethod
    def _clean_text(line):
        import re as _re

        return _re.sub(r"\\[a-z0-9]+\*?", " ", line).strip()


USFM = "\n".join([
    "\\c 5",
    "\\s Jesus heals",
    "\\r (Matt 8:28-34)",
    "\\v 1 First verse.",
    "\\v 2 Second verse.",
    "\\s Another title",
    "\\v 3 Third verse.",
    "\\c 6",
    "\\s Wrong chapter",
    "\\v 1 Other chapter.",
])


def test_headings_are_emitted_in_order_before_their_verse():
    p = _FakeParser({"1": "First verse.", "2": "Second verse.", "3": "Third verse."},
                    content=USFM, target_chapter="5")
    segs = segments_from_usfm(p, level="verse")
    assert [s.seg_id for s in segs] == ["s1", "1", "2", "s2", "3"]
    assert segs[0].text == "Jesus heals"
    # \r cross-reference lines are not headings and must not be timed
    assert all("Matt" not in s.text for s in segs)


def test_headings_respect_target_chapter():
    p = _FakeParser({"1": "First verse."}, content=USFM, target_chapter="5")
    ids = [s.seg_id for s in segments_from_usfm(p, level="verse")]
    assert ids == ["s1", "1"]
    assert "Wrong chapter" not in [s.text for s in segments_from_usfm(p, level="verse")]


def test_headings_can_be_disabled():
    p = _FakeParser({"1": "First verse.", "2": "Second verse.", "3": "Third verse."},
                    content=USFM, target_chapter="5")
    segs = segments_from_usfm(p, level="verse", headings=False)
    assert [s.seg_id for s in segs] == ["1", "2", "3"]


def test_phrase_level_splits_on_separators():
    p = _FakeParser({"1": "One thing. Two things.", "2": "No split here"})
    segs = segments_from_usfm(p, level="phrase")
    assert [s.seg_id for s in segs] == ["1a", "1b", "2"]
    assert segs[0].text == "One thing."


def test_verse_level_keeps_whole_verses_and_drops_empties():
    p = _FakeParser({"1": "One thing. Two things.", "2": "   "})
    segs = segments_from_usfm(p, level="verse")
    assert [s.seg_id for s in segs] == ["1"]
    assert isinstance(segs[0], Segment)
