from vidx.usfm_parser import USFMParser, TimingParser, TextSegmenter, SRTGenerator

SAMPLE_USFM = """\\id MRK
\\c 1
\\s1 The Proclamation of John the Baptist
\\v 1 The beginning of the good news of Jesus Christ, the Son of God. \\f + \\ft Other ancient authorities lack the Son of God\\f*
\\v 2 As it is written in the prophet Isaiah: \\x - \\xo 1.2: \\xt Mal 3.1; Isa 40.3.\\x* "See, I am sending my messenger ahead of you."
"""

SAMPLE_TIMING = """\\c 1
\\level phrase
\\separators . : ; , ? !
0.0\t3.5\ts1
3.5\t7.0\t1a
7.0\t10.5\t1b
10.5\t15.0\t2a
"""


def test_usfm_clean_text():
    parser = USFMParser("")
    raw = "Jesus Christ\\f + \\ft footnote\\f* and God\\x - \\xo ref\\x* with \\fig figure\\fig* done."
    cleaned = parser._clean_text(raw)
    assert "footnote" not in cleaned
    assert "ref" not in cleaned
    assert "figure" not in cleaned
    assert "Jesus Christ" in cleaned
    assert "and God" in cleaned
    assert "done." in cleaned

    # Test variations without space after \\x or \\f, extended tags, and inline references
    raw_variations = "Word\\x- \\xo 1:1 \\xt Gen 1:1\\x* and Spirit\\f+ \\ft note here\\f* with peace\\ex - \\xo 2:2\\ex*."
    cleaned_vars = parser._clean_text(raw_variations)
    assert "Gen 1:1" not in cleaned_vars
    assert "1:1" not in cleaned_vars
    assert "note here" not in cleaned_vars
    assert "2:2" not in cleaned_vars
    assert "Word and Spirit with peace." == cleaned_vars


def test_usfm_parsing():
    parser = USFMParser(SAMPLE_USFM, target_chapter="1")
    assert parser.chapter == "1"
    assert "1" in parser.verses
    assert "2" in parser.verses
    assert "good news" in parser.verses["1"]
    assert "Isaiah:" in parser.verses["2"]
    assert parser.get_section_heading("s1") == "The Proclamation of John the Baptist"


def test_timing_parser():
    tp = TimingParser(SAMPLE_TIMING)
    assert tp.chapter == "1"
    assert tp.level == "phrase"
    assert len(tp.entries) == 4
    assert tp.entries[0]["segment"] == "s1"
    assert tp.entries[1]["start"] == 3.5
    assert tp.entries[1]["end"] == 7.0


def test_text_segmenter():
    sep = [".", ":", ";", ",", "?", "!"]
    segmenter = TextSegmenter(sep)
    text = "The beginning of the good news. Of Jesus Christ, the Son of God."
    segs = segmenter.segment_text(text, 2)
    assert len(segs) == 2
    assert segs[0] == "The beginning of the good news."
    assert "Jesus Christ" in segs[1]


def test_srt_generator():
    up = USFMParser(SAMPLE_USFM, target_chapter="1")
    tp = TimingParser(SAMPLE_TIMING)
    gen = SRTGenerator(up, tp)

    srt_output = gen.generate()
    assert "1" in srt_output
    assert "00:00:00,000 --> 00:00:03,500" in srt_output
    assert "The Proclamation of John the Baptist" in srt_output
    assert "00:00:03,500 --> 00:00:07,000" in srt_output
    assert "good news" in srt_output
