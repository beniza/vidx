"""
ASS Subtitle Generator Module
Converts USFM text + timing data into Advanced SubStation Alpha (.ass) format.
Supports rich styling, section titles, verse numbers, and responsive positioning.
"""
import re
from pathlib import Path
from datetime import timedelta
from usfm_to_srt import TextSegmenter


def hex_to_ass(color_str, default_alpha="00", opacity=None, transparency=None):
    """Convert CSS hex color (#RRGGBB or #RRGGBBAA) or raw ASS color to ASS format (&HAABBGGRR).
    Supports explicit opacity (0.0 to 1.0 or 0 to 100) or transparency (0.0 to 1.0 or 0 to 100)."""
    if not color_str:
        return "&H00FFFFFF"
    
    color_str = str(color_str).strip()
    if color_str.startswith("&H") or color_str.startswith("&h"):
        return color_str.upper()
        
    color = color_str.lstrip("#")
    
    # Determine ASS alpha (00 = opaque, FF = transparent)
    a = default_alpha
    if opacity is not None:
        try:
            op_val = float(opacity)
            if op_val > 1.0:
                op_val /= 100.0
            op_val = max(0.0, min(1.0, op_val))
            ass_a = int(round((1.0 - op_val) * 255))
            a = f"{ass_a:02X}"
        except (ValueError, TypeError):
            pass
    elif transparency is not None:
        try:
            tr_val = float(transparency)
            if tr_val > 1.0:
                tr_val /= 100.0
            tr_val = max(0.0, min(1.0, tr_val))
            ass_a = int(round(tr_val * 255))
            a = f"{ass_a:02X}"
        except (ValueError, TypeError):
            pass
            
    if len(color) == 6:
        r, g, b = color[0:2], color[2:4], color[4:6]
    elif len(color) == 8:
        r, g, b = color[0:2], color[2:4], color[4:6]
        if opacity is None and transparency is None:
            # In CSS, AA=00 is transparent, AA=FF is opaque.
            # In ASS, 00 is opaque, FF is transparent.
            css_a = int(color[6:8], 16)
            ass_a = 255 - css_a
            a = f"{ass_a:02X}"
    else:
        return "&H00FFFFFF"
        
    return f"&H{a}{b.upper()}{g.upper()}{r.upper()}"


def clean_subtitle_text(text):
    """Remove USFM cross-references, footnotes, figures, and stray markers from subtitle text."""
    if not text:
        return ""
    # Remove footnotes \f ... \f* (including nested tags and prefix symbols like +, -)
    text = re.sub(r'\\f\s+.*?\\f\*', '', text, flags=re.DOTALL)
    # Remove cross-references \x ... \x* (including nested tags and prefix symbols like +, -)
    text = re.sub(r'\\x\s+.*?\\x\*', '', text, flags=re.DOTALL)
    # Remove figures \fig ... \fig*
    text = re.sub(r'\\fig\s+.*?\\fig\*', '', text, flags=re.DOTALL)
    # Remove character formatting markers like \bk ... \bk*, \wj ... \wj*, etc.
    text = re.sub(r'\\(?:bk|wj|nd|tl|qs)\s*([^\\]*?)\\(?:bk|wj|nd|tl|qs)\*', r'\1', text)
    # Remove all remaining USFM markers (but keep the text after them)
    text = re.sub(r'\\[a-z0-9]+\*?', ' ', text)
    # Clean up standalone + or * or extra whitespace
    text = re.sub(r'\s*\+\s*', ' ', text)
    text = re.sub(r'\s*\*\s*', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text



class ASSGenerator:
    """Generate Advanced SubStation Alpha (.ass) subtitle files from USFM and Timing data."""
    
    def __init__(self, usfm_parser, timing_parser, config=None):
        self.usfm = usfm_parser
        self.timing = timing_parser
        self.segmenter = TextSegmenter(timing_parser.separators)
        self.config = config or {}
        
        # Load video defaults
        video_cfg = self.config.get("video", {})
        res_str = video_cfg.get("resolution", "1920x1080")
        if "x" in res_str:
            self.res_x, self.res_y = map(int, res_str.split("x"))
        else:
            self.res_x, self.res_y = 1920, 1080
            
        # Load style defaults
        style_cfg = self.config.get("style", {})
        self.verse_style = style_cfg.get("verse", {})
        self.heading_style = style_cfg.get("heading", {})
        self.num_style = style_cfg.get("verse_number", {})
        
    def _format_timestamp(self, seconds):
        """Convert seconds to ASS timestamp format: H:MM:SS.cs"""
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        centis = int(round((seconds - total_seconds) * 100))
        
        if centis >= 100:
            secs += 1
            centis -= 100
            if secs >= 60:
                minutes += 1
                secs -= 60
                if minutes >= 60:
                    hours += 1
                    minutes -= 60
                    
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"
        
    def _parse_segment_id(self, segment_id):
        """
        Parse segment ID like '2a', '15c', 's1', '9'
        Returns: (verse_num or section_marker, segment_letter or None)
        """
        if segment_id.startswith('s'):
            return ('section', segment_id)
            
        match = re.match(r'^(\d+)([a-z])?$', segment_id)
        if match:
            verse_num = match.group(1)
            segment_letter = match.group(2)
            return (verse_num, segment_letter)
            
        return (None, None)
        
    def _get_script_info_header(self):
        """Generate [Script Info] section"""
        book_id = getattr(self.usfm, "book_id", "Scripture")
        chapter = getattr(self.usfm, "chapter", "1")
        title = f"{book_id} Chapter {chapter}"
        
        return [
            "[Script Info]",
            f"Title: {title}",
            "ScriptType: v4.00+",
            "WrapStyle: 0",  # Smart wrapping, bottom up
            f"PlayResX: {self.res_x}",
            f"PlayResY: {self.res_y}",
            "ScaledBorderAndShadow: yes",
            ""
        ]
        
    def _get_styles_section(self):
        """Generate [V4+ Styles] section"""
        # Extract verse styling properties
        v_font = self.verse_style.get("font", "Nirmala UI")
        v_size = self.verse_style.get("size", 48)
        v_color = hex_to_ass(self.verse_style.get("color", "#FFFFFF"))
        v_outline_col = hex_to_ass(self.verse_style.get("outline_color", "#000000"))
        v_outline = self.verse_style.get("outline_width", 3)
        v_shadow = self.verse_style.get("shadow", 1)
        v_align = self.verse_style.get("alignment", 2)  # 2 = bottom center
        v_margin_b = self.verse_style.get("margin_bottom", 60)
        v_margin_lr = self.verse_style.get("margin_lr", 60)
        
        # Background box for verse
        if self.verse_style.get("background_box", True):
            v_op = self.verse_style.get("background_opacity", self.verse_style.get("opacity", None))
            v_tr = self.verse_style.get("background_transparency", self.verse_style.get("transparency", None))
            v_bg_col = hex_to_ass(self.verse_style.get("background_color", "#00000080"), default_alpha="80", opacity=v_op, transparency=v_tr)
            v_border_style = 3  # 3 = opaque box around text
        else:
            v_bg_col = "&H00000000"
            v_border_style = 1  # 1 = outline + shadow
            
        # Extract heading styling properties
        h_font = self.heading_style.get("font", v_font)
        h_size = self.heading_style.get("size", int(v_size * 1.15))
        h_color = hex_to_ass(self.heading_style.get("color", "#FFD400"))
        h_outline_col = hex_to_ass(self.heading_style.get("outline_color", "#000000"))
        h_outline = self.heading_style.get("outline_width", v_outline)
        h_shadow = self.heading_style.get("shadow", v_shadow)
        h_align = self.heading_style.get("alignment", 8)  # 8 = top center
        h_margin_v = self.heading_style.get("margin_vertical", 80)
        h_bold = -1 if self.heading_style.get("bold", True) else 0
        
        # Background box for heading
        if self.heading_style.get("background_box", True):
            h_op = self.heading_style.get("background_opacity", self.heading_style.get("opacity", None))
            h_tr = self.heading_style.get("background_transparency", self.heading_style.get("transparency", None))
            h_bg_col = hex_to_ass(self.heading_style.get("background_color", "#00000080"), default_alpha="80", opacity=h_op, transparency=h_tr)
            h_border_style = 3
        else:
            h_bg_col = "&H00000000"
            h_border_style = 1
            
        lines = [
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Verse,{v_font},{v_size},{v_color},&H000000FF,{v_outline_col},{v_bg_col},0,0,0,0,100,100,0,0,{v_border_style},{v_outline},{v_shadow},{v_align},{v_margin_lr},{v_margin_lr},{v_margin_b},1",
            f"Style: Heading,{h_font},{h_size},{h_color},&H000000FF,{h_outline_col},{h_bg_col},{h_bold},0,0,0,100,100,0,0,{h_border_style},{h_outline},{h_shadow},{h_align},{v_margin_lr},{v_margin_lr},{h_margin_v},1",
            ""
        ]
        return lines
        
    def generate(self, start_counter=1):
        """
        Generate ASS content string.
        """
        lines = []
        lines.extend(self._get_script_info_header())
        lines.extend(self._get_styles_section())
        
        lines.append("[Events]")
        lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
        
        # First pass: identify verses that have segments
        verse_segments_map = {}
        for entry in self.timing.entries:
            verse_num, segment_letter = self._parse_segment_id(entry['segment'])
            if verse_num != 'section':
                if verse_num not in verse_segments_map:
                    verse_segments_map[verse_num] = []
                verse_segments_map[verse_num].append(entry)
                
        # Pre-split verses that have multiple segments
        verse_text_segments = {}
        for verse_num, entries in verse_segments_map.items():
            verse_text = clean_subtitle_text(self.usfm.get_verse_text(verse_num))
            if not verse_text:
                continue
            has_segments = any(self._parse_segment_id(e['segment'])[1] is not None for e in entries)
            if has_segments and len(entries) > 1:
                segments = self.segmenter.segment_text(verse_text, len(entries))
                verse_text_segments[verse_num] = segments
            else:
                verse_text_segments[verse_num] = [verse_text]
                
        # Verse numbering formatting options
        show_num = self.num_style.get("show", True)
        num_color = hex_to_ass(self.num_style.get("color", "#FFC080"))
        num_size = self.num_style.get("size", int(self.verse_style.get("size", 48) * 0.75))
        book_name = getattr(self.usfm, "book_name", "") or getattr(self.usfm, "book_id", "")
        chapter_num = getattr(self.usfm, "chapter", "") or getattr(self.timing, "chapter", "")
        
        # Track which verse numbers we've already displayed if we only want them once per verse
        # (By default, inline numbering appears on segment 'a' or unsegmented verse)
        num_on_every_segment = self.num_style.get("on_every_segment", False)
        seen_verses = set()
        
        # Second pass: generate ASS dialogue events
        for entry in self.timing.entries:
            verse_num, segment_letter = self._parse_segment_id(entry['segment'])
            text = ''
            style = 'Verse'
            
            if verse_num == 'section':
                style = 'Heading'
                section_marker = segment_letter
                text = clean_subtitle_text(self.usfm.get_section_heading(section_marker))
            else:
                style = 'Verse'
                if verse_num in verse_text_segments:
                    segments = verse_text_segments[verse_num]
                    if segment_letter:
                        segment_index = ord(segment_letter) - ord('a')
                        if segment_index < len(segments):
                            text = segments[segment_index]
                    else:
                        text = segments[0] if segments else ''
                        
                # Add verse number formatting if enabled
                if show_num and text and (num_on_every_segment or verse_num not in seen_verses):
                    seen_verses.add(verse_num)
                    ref_str = f"{book_name} {chapter_num}:{verse_num}".strip()
                    if ref_str.startswith(":"):
                        ref_str = ref_str[1:].strip()
                    # Inline override tag: change color & size, then reset with \r
                    num_tag = f"{{\\c{num_color}\\fs{num_size}}}{ref_str}{{\\rVerse}}\\N"
                    text = f"{num_tag}{text}"
                    
            if text:
                start_str = self._format_timestamp(entry['start'])
                end_str = self._format_timestamp(entry['end'])
                # Clean any stray newlines in text
                text = text.replace("\r\n", "\\N").replace("\n", "\\N")
                lines.append(f"Dialogue: 0,{start_str},{end_str},{style},,0,0,0,,{text}")
                
        return "\n".join(lines)


def convert_to_ass(usfm_file, timing_file, output_file=None, config=None):
    """
    Convert USFM + timing file to ASS subtitle file.
    """
    from usfm_to_srt import USFMParser, TimingParser
    
    usfm_path = Path(usfm_file)
    timing_path = Path(timing_file)
    
    if not usfm_path.exists():
        print(f"[-] USFM file not found: {usfm_path}")
        return False
    if not timing_path.exists():
        print(f"[-] Timing file not found: {timing_path}")
        return False
        
    if output_file is None:
        output_file = usfm_path.with_suffix('.ass')
    else:
        output_file = Path(output_file)
        
    usfm_content = usfm_path.read_text(encoding='utf-8')
    timing_content = timing_path.read_text(encoding='utf-8')
    
    timing_parser = TimingParser(timing_content)
    usfm_parser = USFMParser(usfm_content, target_chapter=timing_parser.chapter)
    
    # Extract book name if available
    for line in usfm_content.split('\n'):
        if line.startswith('\\h '):
            usfm_parser.book_name = line[3:].strip()
            break
        elif line.startswith('\\id '):
            usfm_parser.book_id = line[4:].split()[0].strip()
            
    generator = ASSGenerator(usfm_parser, timing_parser, config=config)
    ass_content = generator.generate()
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(ass_content, encoding='utf-8')
    return True
