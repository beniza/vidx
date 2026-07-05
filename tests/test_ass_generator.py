import pytest
from vidx.ass_generator import hex_to_ass, clean_subtitle_text, ASSGenerator
from vidx.usfm_parser import USFMParser, TimingParser


def test_hex_to_ass_conversions():
    # 6-digit hex (#RRGGBB) -> &HAABBGGRR with default alpha 00
    assert hex_to_ass("#FFFFFF") == "&H00FFFFFF"
    assert hex_to_ass("#FFD400") == "&H0000D4FF"
    
    # Already ASS format
    assert hex_to_ass("&H00FFFFFF") == "&H00FFFFFF"
    
    # 8-digit hex (#RRGGBBAA where AA is CSS opacity: 00=trans, FF=opaque)
    # CSS #00000080 -> ASS alpha should invert CSS alpha (255 - 128 = 127 = 7F)
    assert hex_to_ass("#00000080") == "&H7F000000"
    
    # Explicit opacity (0.0 to 1.0)
    assert hex_to_ass("#000000", opacity=0.60) == "&H66000000"
    
    # Explicit transparency percentage (0 to 100)
    assert hex_to_ass("#000000", transparency=40) == "&H66000000"
    
    # Default fallback when None or empty
    assert hex_to_ass(None) == "&H00FFFFFF"


def test_clean_subtitle_text():
    raw = "Jesus\\f + \\ft note\\f* said,\\x - \\xo 1.1\\x* 'Peace.'"
    assert clean_subtitle_text(raw) == "Jesus said, 'Peace.'"
    raw_variations = "Word\\x- \\xo 1:1 \\xt Gen 1:1\\x* and Spirit\\f+ \\ft note here\\f* with peace\\ex - \\xo 2:2\\ex*."
    assert clean_subtitle_text(raw_variations) == "Word and Spirit with peace."


def test_ass_generator():
    usfm_data = "\\id MRK\n\\c 1\n\\s1 John Baptizes\n\\v 1 In the beginning was the Word.\n\\v 2 He was with God."
    timing_data = "\\c 1\n\\level phrase\n\\separators . : ; , ? !\n0.0\t2.0\ts1\n2.0\t5.0\t1a\n5.0\t8.0\t2a"
    
    up = USFMParser(usfm_data, target_chapter="1")
    tp = TimingParser(timing_data)
    
    config = {
        "video": {"resolution": "1920x1080"},
        "style": {
            "verse": {
                "font": "Bailey",
                "size": 50,
                "color": "#FFFFFF",
                "background_box": True,
                "background_color": "#000000",
                "background_opacity": 0.70
            },
            "heading": {
                "font": "Bailey",
                "size": 60,
                "color": "#FFD400"
            },
            "verse_number": {
                "show": True,
                "color": "#FFC080"
            }
        }
    }
    
    gen = ASSGenerator(up, tp, config=config)
    ass_content = gen.generate()
    
    assert "[Script Info]" in ass_content
    assert "PlayResX: 1920" in ass_content
    assert "PlayResY: 1080" in ass_content
    assert "[V4+ Styles]" in ass_content
    assert "Style: Verse,Bailey,50" in ass_content
    assert "Style: Heading,Bailey,60" in ass_content
    assert "[Events]" in ass_content
    
    # Check dialogue line formatting and background box drawing in styles
    assert "Dialogue: 0,0:00:00.00,0:00:02.00,Heading," in ass_content
    assert "John Baptizes" in ass_content
    assert "Style: Verse,Bailey,50,&H00FFFFFF,&H000000FF,&H00000000,&H4D000000,0,0,0,0,100,100,0,0,3," in ass_content
    assert "In the beginning was the Word." in ass_content
