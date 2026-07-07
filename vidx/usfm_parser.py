"""
USFM to SRT Converter
Converts USFM Bible files + timing files to SRT subtitle format
Supports single chapter or batch processing for entire books
"""

import sys
import re
from pathlib import Path
from datetime import timedelta
import glob

# Import validation module (optional)
try:
    from validator import BatchValidator, USFM_GRAMMAR_AVAILABLE

    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    USFM_GRAMMAR_AVAILABLE = False

from . import __version__


class USFMParser:
    """Parse USFM files and extract verse text"""

    def __init__(self, usfm_content, target_chapter=None):
        self.content = usfm_content
        self.target_chapter = target_chapter  # Only parse this chapter
        self.verses = {}  # verse_num -> full_text
        self.sections = {}  # section_marker (s1, s2, etc.) -> heading_text
        self.chapter = None
        self._parse()

    def _clean_text(self, text):
        """Remove USFM markers and notes from text"""
        # Remove footnotes \f, \fe, \ef, \fqa (everything between including nested markers and prefix symbols)
        text = re.sub(
            r"\\(?:f|fe|ef|fqa)\b.*?\\(?:f|fe|ef|fqa)\*", "", text, flags=re.DOTALL
        )

        # Remove cross-references \x, \ex, \rq, \esb, \cat (everything between including nested markers and prefix symbols)
        text = re.sub(
            r"\\(?:x|ex|rq|esb|cat)\b.*?\\(?:x|ex|rq|esb|cat)\*",
            "",
            text,
            flags=re.DOTALL,
        )

        # Remove figures \fig ... \fig*
        text = re.sub(r"\\fig\b.*?\\fig\*", "", text, flags=re.DOTALL)

        # Remove character formatting markers like \bk ... \bk*, \wj ... \wj*, etc.
        text = re.sub(
            r"\\(?:bk|wj|nd|tl|qs)\s*([^\\]*?)\\(?:bk|wj|nd|tl|qs)\*", r"\1", text
        )

        # Remove all remaining USFM markers (but keep the text after them)
        # This handles \q1, \q2, \p, \m, \v, \fr, \xo, \xt, etc.
        text = re.sub(r"\\[a-z0-9]+\*?", " ", text)

        # Clean up extra spaces and special characters left behind
        text = re.sub(r"\s*\+\s*", " ", text)  # Remove standalone +
        text = re.sub(r"\s*\*\s*", " ", text)  # Remove standalone *
        text = re.sub(r"\s+", " ", text)  # Normalize whitespace
        text = text.strip()

        return text

    def _parse(self):
        """Parse USFM content and extract verses and sections"""
        lines = self.content.split("\n")

        current_verse = None
        current_verse_text = []
        section_counter = 0
        in_target_chapter = False  # Track if we're in the target chapter

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Extract chapter number
            if line.startswith("\\c "):
                self.chapter = line[3:].strip()

                # Check if this is our target chapter
                if self.target_chapter:
                    try:
                        in_target_chapter = int(self.chapter) == int(self.target_chapter)
                    except (ValueError, TypeError):
                        in_target_chapter = str(self.chapter).strip() == str(self.target_chapter).strip()

                    # If we've passed our target chapter, stop parsing
                    try:
                        if self.chapter and int(self.chapter) > int(self.target_chapter):
                            self.chapter = str(self.target_chapter)
                            break
                    except (ValueError, TypeError):
                        pass
                else:
                    in_target_chapter = (
                        True  # Parse all chapters if no target specified
                    )

                # Reset counters when entering new chapter
                if in_target_chapter:
                    section_counter = 0

                continue

            # Only process if we're in the target chapter (or no target specified)
            if not in_target_chapter:
                continue

            # Extract section headings
            if line.startswith("\\s"):
                section_counter += 1
                # Get the heading text (everything after \s, \s1, \s2, etc.)
                heading = re.sub(r"^\\s\d*\s*", "", line)
                heading = self._clean_text(heading)
                if heading:
                    self.sections[f"s{section_counter}"] = heading
                continue

            # Skip intro materials and headers
            if line.startswith(
                (
                    "\\id",
                    "\\h",
                    "\\toc",
                    "\\mt",
                    "\\imt",
                    "\\im",
                    "\\is",
                    "\\io",
                    "\\iot",
                    "\\r",
                    "\\ip",
                )
            ):
                continue

            # Extract verse number and text
            verse_match = re.match(r"^\\v\s+(\d+(?:-\d+)?)\s+(.*)$", line)
            if verse_match:
                # Save previous verse if exists
                if current_verse is not None and current_verse_text:
                    full_text = " ".join(current_verse_text)
                    self.verses[current_verse] = self._clean_text(full_text)

                # Start new verse
                current_verse = verse_match.group(1)
                current_verse_text = [verse_match.group(2)]
                continue

            # Continuation of current verse (poetry, paragraphs, etc.)
            if current_verse is not None and line.startswith("\\"):
                # This is a continuation line (like \q1, \q2, \p, \m)
                text = line
                current_verse_text.append(text)

        # Save last verse
        if current_verse is not None and current_verse_text:
            full_text = " ".join(current_verse_text)
            self.verses[current_verse] = self._clean_text(full_text)

    def get_verse_text(self, verse_num):
        """Get text for a specific verse number"""
        return self.verses.get(str(verse_num), "")

    def get_section_heading(self, section_marker):
        """Get section heading text (e.g., 's1', 's2')"""
        return self.sections.get(section_marker, "")


class TimingParser:
    """Parse timing files"""

    def __init__(self, timing_content, filepath=None):
        self.entries = []
        self.level = None
        self.separators = []
        self.chapter = None
        self._parse(timing_content)
        if self.chapter is None and filepath:
            name = Path(filepath).name
            m = (
                re.search(r"(?:[_-]|\b)(?:Ch|Chapter|Chp|c)[_-]?(\d+)", name, re.IGNORECASE)
                or re.search(r"[_-](\d{1,3})[_-]?(?:timing|\.txt|\.tsv|\b)", name, re.IGNORECASE)
                or re.search(r"(?:[_-]|\b)(?:Chapter|Ch|Chp)[_-]?(\d+)", name, re.IGNORECASE)
            )
            if m:
                try:
                    self.chapter = str(int(m.group(1)))
                except ValueError:
                    self.chapter = m.group(1)

    def _parse(self, content):
        """Parse timing file"""
        lines = content.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Extract chapter from timing file
            if line.startswith("\\c"):
                self.chapter = line.split()[1] if len(line.split()) > 1 else None
                continue

            # Skip other USFM markers
            if line.startswith("\\id"):
                continue

            # Extract level
            if line.startswith("\\level"):
                self.level = line.split()[1] if len(line.split()) > 1 else None
                continue

            # Extract separators
            if line.startswith("\\separators"):
                # Get everything after \separators
                sep_text = line[12:].strip()
                # Split by spaces to get individual separators
                self.separators = sep_text.split()
                continue

            # Parse timing entries: start_time end_time segment_id
            parts = line.split("\t")
            if len(parts) >= 3:
                try:
                    start_time = float(parts[0])
                    end_time = float(parts[1])
                    segment_id = parts[2]

                    self.entries.append(
                        {"start": start_time, "end": end_time, "segment": segment_id}
                    )
                except ValueError:
                    # Skip lines that don't have valid numbers
                    continue

    def shift_timestamps(self, offset_seconds: float):
        """Shift all start and end timestamps by offset_seconds (for audio intros/bumpers)."""
        if not offset_seconds or offset_seconds == 0:
            return
        for entry in self.entries:
            entry["start"] += offset_seconds
            entry["end"] += offset_seconds


class TextSegmenter:
    """Split verse text into segments based on separators"""

    def __init__(self, separators):
        self.separators = separators

    def segment_text(self, text, num_segments):
        """
        Split text into specified number of segments using separators
        Returns list of text segments
        """
        if num_segments == 1:
            return [text]

        # Create regex pattern from separators
        # Escape special regex characters
        escaped_seps = [re.escape(sep) for sep in self.separators]
        pattern = f"([{''.join(escaped_seps)}])"

        # Split text but keep separators
        parts = re.split(pattern, text)

        # Reconstruct segments with separators attached
        segments = []
        current = ""

        for part in parts:
            if not part:
                continue

            current += part

            # If this part is a separator, we complete a segment
            if part in self.separators:
                segments.append(current.strip())
                current = ""

        # Add any remaining text
        if current.strip():
            segments.append(current.strip())

        # If we have more segments than needed, merge the extras
        if len(segments) > num_segments:
            # Keep first (num_segments - 1) segments as-is
            # Merge remaining into last segment
            merged_last = " ".join(segments[num_segments - 1 :])
            segments = segments[: num_segments - 1] + [merged_last]

        # If we have fewer segments than needed, just return what we have
        # The matching will handle missing segments gracefully

        return segments


class SRTGenerator:
    """Generate SRT subtitle file"""

    def __init__(self, usfm_parser, timing_parser):
        self.usfm = usfm_parser
        self.timing = timing_parser
        self.segmenter = TextSegmenter(timing_parser.separators)

    def _format_timestamp(self, seconds):
        """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        millis = int((seconds - total_seconds) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _parse_segment_id(self, segment_id):
        """
        Parse segment ID like '2a', '15c', 's1', '9'
        Returns: (verse_num or section_marker, segment_letter or None)
        """
        # Check if it's a section marker (s1, s2, etc.)
        if segment_id.startswith("s"):
            return ("section", segment_id)

        # Parse verse number with optional segment letter
        match = re.match(r"^(\d+)([a-z])?$", segment_id)
        if match:
            verse_num = match.group(1)
            segment_letter = match.group(2)
            return (verse_num, segment_letter)

        return (None, None)

    def _get_text_for_segment(self, verse_num, segment_letter, verse_segments):
        """Get text for a specific segment"""
        if segment_letter is None:
            # Return full verse
            return self.usfm.get_verse_text(verse_num)

        # Get segment by letter (a=0, b=1, c=2, etc.)
        segment_index = ord(segment_letter) - ord("a")

        if segment_index < len(verse_segments):
            return verse_segments[segment_index]

        return ""

    def generate(self, start_counter=1):
        """
        Generate SRT content

        Args:
            start_counter: Starting subtitle number (for combined mode)
        """
        srt_lines = []
        subtitle_counter = start_counter

        # First pass: identify verses that have segments
        verse_segments_map = {}  # verse_num -> list of timing entries

        for entry in self.timing.entries:
            verse_num, segment_letter = self._parse_segment_id(entry["segment"])

            if verse_num != "section":
                if verse_num not in verse_segments_map:
                    verse_segments_map[verse_num] = []
                verse_segments_map[verse_num].append(entry)

        # Pre-split verses that have multiple segments
        verse_text_segments = {}  # verse_num -> list of text segments

        for verse_num, entries in verse_segments_map.items():
            verse_text = self.usfm.get_verse_text(verse_num)
            if not verse_text:
                continue

            # Check if this verse has segments (entries with letters)
            has_segments = any(
                self._parse_segment_id(e["segment"])[1] is not None for e in entries
            )

            if has_segments and len(entries) > 1:
                # Split the verse text into segments
                segments = self.segmenter.segment_text(verse_text, len(entries))
                verse_text_segments[verse_num] = segments
            else:
                # No segments, keep full text
                verse_text_segments[verse_num] = [verse_text]

        # Second pass: generate SRT in original timing file order
        for entry in self.timing.entries:
            verse_num, segment_letter = self._parse_segment_id(entry["segment"])

            text = ""

            if verse_num == "section":
                # Section heading
                section_marker = segment_letter
                text = self.usfm.get_section_heading(section_marker)
            else:
                # Regular verse
                if verse_num in verse_text_segments:
                    segments = verse_text_segments[verse_num]

                    if segment_letter:
                        # Get specific segment by letter
                        segment_index = ord(segment_letter) - ord("a")
                        if segment_index < len(segments):
                            text = segments[segment_index]
                    else:
                        # No letter, use full text (first segment)
                        text = segments[0] if segments else ""

            # Add to SRT if we have text
            if text:
                srt_lines.append(str(subtitle_counter))
                srt_lines.append(
                    f"{self._format_timestamp(entry['start'])} --> "
                    f"{self._format_timestamp(entry['end'])}"
                )
                srt_lines.append(text)
                srt_lines.append("")  # Blank line between subtitles
                subtitle_counter += 1

        return "\n".join(srt_lines)


def convert_to_srt(usfm_file, timing_file, output_file=None, config=None):
    """
    Convert USFM + timing file to SRT

    Args:
        usfm_file: Path to USFM file
        timing_file: Path to timing file
        output_file: Path to output SRT file (optional)
        config: Optional project/bumper configuration dict
    """
    usfm_path = Path(usfm_file)
    timing_path = Path(timing_file)

    if not usfm_path.exists():
        print(f"[-] USFM file not found: {usfm_path}")
        return False

    if not timing_path.exists():
        print(f"[-] Timing file not found: {timing_path}")
        return False

    # Default output file
    if output_file is None:
        output_file = usfm_path.with_suffix(".srt")
    else:
        output_file = Path(output_file)

    print("\n[*] Processing:")
    print(f"   USFM:   {usfm_path.name}")
    print(f"   Timing: {timing_path.name}")

    try:
        # Read files
        usfm_content = usfm_path.read_text(encoding="utf-8")
        timing_content = timing_path.read_text(encoding="utf-8")

        # Parse timing file first to get chapter number
        timing_parser = TimingParser(timing_content, filepath=timing_path)

        offset_seconds = 0.0
        if config:
            bumpers_cfg = config.get("bumpers", {})
            video_cfg = config.get("video", {})
            if "_calc_intro_duration" in bumpers_cfg:
                offset_seconds = float(bumpers_cfg["_calc_intro_duration"])
            elif (
                bumpers_cfg.get("intro_audio")
                and Path(bumpers_cfg["intro_audio"]).exists()
            ):
                from .bumpers import get_media_duration

                offset_seconds = get_media_duration(bumpers_cfg["intro_audio"])
            elif video_cfg.get("title_image") or bumpers_cfg.get("title_image"):
                offset_seconds = float(
                    video_cfg.get("title_duration")
                    or bumpers_cfg.get("title_duration")
                    or 3.0
                )

        if offset_seconds > 0:
            timing_parser.shift_timestamps(offset_seconds)

        # Parse USFM with target chapter from timing file
        usfm_parser = USFMParser(usfm_content, target_chapter=timing_parser.chapter)

        print(f"   Verses: {len(usfm_parser.verses)}")
        print(f"   Timing entries: {len(timing_parser.entries)}")
        print(f"   Separators: {timing_parser.separators}")

        # Generate SRT
        generator = SRTGenerator(usfm_parser, timing_parser)
        srt_content = generator.generate()

        # Write output
        output_file.write_text(srt_content, encoding="utf-8")

        # Count subtitles
        subtitle_count = srt_content.count("\n\n")

        print("\n[+] Success!")
        print(f"   Output: {output_file}")
        print(f"   Subtitles: {subtitle_count}")

        return True

    except Exception as e:
        print(f"\n[-] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def find_timing_files(timing_path):
    """
    Find all timing files from a path (file, folder, or pattern)

    Args:
        timing_path: Path to timing file, folder, or glob pattern

    Returns:
        List of timing file paths sorted by chapter number
    """
    timing_path = Path(timing_path)
    timing_files = []

    if timing_path.is_file():
        # Single file
        timing_files = [timing_path]
    elif timing_path.is_dir():
        # Directory - find all .txt files
        timing_files = list(timing_path.glob("*.txt"))
    else:
        # Try as glob pattern
        pattern_str = str(timing_path)
        timing_files = [Path(f) for f in glob.glob(pattern_str)]

    # Sort by chapter number if possible
    def extract_chapter(filepath):
        """Extract chapter number from filename like C01-01-MRK-01-timing.txt"""
        match = re.search(r"C(\d+)", filepath.name)
        return int(match.group(1)) if match else 0

    timing_files.sort(key=extract_chapter)
    return timing_files


def convert_batch(usfm_file, timing_files, output_folder=None, combined=False):
    """
    Convert multiple chapters to SRT

    Args:
        usfm_file: Path to USFM file (whole book)
        timing_files: List of timing file paths
        output_folder: Output folder for individual SRT files
        combined: If True, combine all chapters into one SRT file

    Returns:
        True if all conversions succeeded
    """
    usfm_path = Path(usfm_file)

    if not usfm_path.exists():
        print(f"[-] USFM file not found: {usfm_path}")
        return False

    if not timing_files:
        print("[-] No timing files found")
        return False

    # Setup output folder
    if output_folder:
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
    else:
        output_folder = usfm_path.parent

    print("\n[*] Batch Processing:")
    print(f"   USFM:    {usfm_path.name}")
    print(f"   Chapters: {len(timing_files)}")
    print(f"   Output:  {output_folder}")
    print(f"   Mode:    {'Combined' if combined else 'Separate files'}")
    print("")

    success_count = 0
    failed_count = 0
    empty_count = 0
    all_srt_content = []
    subtitle_offset = 1  # For combined mode

    for i, timing_file in enumerate(timing_files, 1):
        timing_path = Path(timing_file)

        if not timing_path.exists():
            print(
                f"  [{i}/{len(timing_files)}] [-] Timing file not found: {timing_path.name}"
            )
            failed_count += 1
            continue

        try:
            # Read files
            usfm_content = usfm_path.read_text(encoding="utf-8")
            timing_content = timing_path.read_text(encoding="utf-8")

            # Parse timing file first to get chapter number
            timing_parser = TimingParser(timing_content, filepath=timing_path)
            chapter_num = timing_parser.chapter or "unknown"

            # Parse USFM with target chapter
            usfm_parser = USFMParser(usfm_content, target_chapter=timing_parser.chapter)

            # Generate SRT
            generator = SRTGenerator(usfm_parser, timing_parser)

            if combined:
                # Generate with offset for combined mode
                srt_content = generator.generate(subtitle_offset)
                all_srt_content.append(srt_content)
                # Update offset for next chapter
                subtitle_offset += srt_content.count("\n\n")
            else:
                # Generate separate file
                srt_content = generator.generate()

                # Determine output filename
                output_file = output_folder / f"{usfm_path.stem}_ch{chapter_num}.srt"
                output_file.write_text(srt_content, encoding="utf-8")

            subtitle_count = srt_content.count("\n\n")

            if subtitle_count == 0:
                print(
                    f"  [{i}/{len(timing_files)}] [!] Chapter {chapter_num}: 0 subtitles (timing file may not match USFM)"
                )
                empty_count += 1
            else:
                print(
                    f"  [{i}/{len(timing_files)}] [+] Chapter {chapter_num}: {subtitle_count} subtitles"
                )

            success_count += 1

        except Exception as e:
            print(
                f"  [{i}/{len(timing_files)}] [-] Error processing {timing_path.name}: {e}"
            )
            failed_count += 1

    # Write combined file if requested
    if combined and all_srt_content:
        combined_file = output_folder / f"{usfm_path.stem}_complete.srt"
        combined_content = "\n".join(all_srt_content)
        combined_file.write_text(combined_content, encoding="utf-8")
        total_subtitles = combined_content.count("\n\n")
        print(f"\n[+] Combined SRT: {combined_file.name}")
        print(f"   Total subtitles: {total_subtitles}")

    print(f"\n{'='*60}")
    print(f"[+] Completed: {success_count} succeeded, {failed_count} failed")
    if empty_count > 0:
        print(f"[!] Warning: {empty_count} chapter(s) produced 0 subtitles")
        print("    (Timing files may be for different book than USFM)")
    print(f"{'='*60}")

    return failed_count == 0


def main():
    """Main entry point"""
    print("=" * 60)
    print(f"  USFM to SRT Converter v{__version__}")
    print("=" * 60)

    # Parse arguments
    args = sys.argv[1:]
    combined = "--combined" in args
    if combined:
        args.remove("--combined")

    # Check for validation flags
    validate_only = "--validate" in args
    if validate_only:
        args.remove("--validate")

    skip_validation = "--skip-validation" in args
    if skip_validation:
        args.remove("--skip-validation")

    if len(args) < 2:
        print("""
Usage - Single Chapter:
  python usfm_to_srt.py <usfm_file> <timing_file> [output_file]

Usage - Multiple Chapters (Batch):
  python usfm_to_srt.py <usfm_file> <timing_folder> [output_folder]
  python usfm_to_srt.py <usfm_file> <timing_folder> [output_folder] --combined

Usage - Validation Only:
  python usfm_to_srt.py <usfm_file> <timing_folder> --validate

Examples:
  # Single chapter
  python usfm_to_srt.py 42MRK.SFM C01-01-MRK-01-timing.txt
  python usfm_to_srt.py 42MRK.SFM C01-01-MRK-01-timing.txt output.srt
  
  # Batch processing (folder of timing files)
  python usfm_to_srt.py 42MRK.SFM ./timing_files/ ./output/
  
  # Batch with combined output (single SRT for entire book)
  python usfm_to_srt.py 42MRK.SFM ./timing_files/ ./output/ --combined

Input files:
  - USFM file: Bible text in USFM format (whole book)
  - Timing file: Single .txt file for one chapter
  - Timing folder: Folder containing multiple timing files

Options:
  --combined          Combine all chapters into one SRT file (batch mode only)
  --validate          Validate files only (no conversion)
  --skip-validation   Skip validation and proceed directly to conversion

Output:
  - SRT file(s): Standard subtitle format for video
        """)
        sys.exit(1)

    usfm_file = args[0]
    timing_input = args[1]
    output = args[2] if len(args) > 2 else None

    # Detect batch or single mode
    timing_path = Path(timing_input)

    if timing_path.is_dir():
        # Batch mode: folder of timing files
        timing_files = find_timing_files(timing_path)
        if not timing_files:
            print(f"\n[-] No timing files found in: {timing_path}")
            sys.exit(1)

        # Run validation if requested or available (unless skipped)
        if VALIDATION_AVAILABLE and not skip_validation:
            validator = BatchValidator()
            reports, all_valid = validator.validate_conversion(
                usfm_file, timing_files, verbose=True
            )

            if validate_only:
                # Just validate, don't convert
                print(validator.generate_summary(reports))
                sys.exit(0 if all_valid else 1)

            if not all_valid:
                print("\n[-] Validation failed. Fix errors before converting.")
                print("    Use --skip-validation to convert anyway (not recommended).")
                print(validator.generate_summary(reports))
                sys.exit(1)

            print("\n[+] Validation passed! Proceeding with conversion...\n")
        elif not VALIDATION_AVAILABLE:
            if validate_only:
                print("\n[-] Error: Validation module not available.")
                print("    Install dependencies: pip install -r requirements.txt")
                sys.exit(1)
            print("\n[!] Note: Validation skipped (usfm-grammar not installed)")
            print("    Install with: pip install usfm-grammar==3.1.2\n")

        success = convert_batch(usfm_file, timing_files, output, combined=combined)
    elif timing_path.exists() and timing_path.is_file():
        # Single mode: one timing file
        if combined:
            print("\n[!] Warning: --combined flag ignored (single file mode)")

        # Run validation if requested
        if VALIDATION_AVAILABLE and not skip_validation:
            validator = BatchValidator()
            reports, all_valid = validator.validate_conversion(
                usfm_file, [timing_input], verbose=True
            )

            if validate_only:
                print(validator.generate_summary(reports))
                sys.exit(0 if all_valid else 1)

            if not all_valid:
                print("\n[-] Validation failed. Fix errors before converting.")
                print("    Use --skip-validation to convert anyway (not recommended).")
                sys.exit(1)

            print("\n[+] Validation passed! Proceeding with conversion...\n")
        elif not VALIDATION_AVAILABLE and validate_only:
            print("\n[-] Error: Validation module not available.")
            print("    Install dependencies: pip install -r requirements.txt")
            sys.exit(1)

        success = convert_to_srt(usfm_file, timing_input, output)
    else:
        # Try as glob pattern
        timing_files = find_timing_files(timing_input)
        if timing_files:
            # Run validation if requested
            if VALIDATION_AVAILABLE and not skip_validation:
                validator = BatchValidator()
                reports, all_valid = validator.validate_conversion(
                    usfm_file, timing_files, verbose=True
                )

                if validate_only:
                    print(validator.generate_summary(reports))
                    sys.exit(0 if all_valid else 1)

                if not all_valid:
                    print("\n[-] Validation failed. Fix errors before converting.")
                    print(
                        "    Use --skip-validation to convert anyway (not recommended)."
                    )
                    sys.exit(1)

                print("\n[+] Validation passed! Proceeding with conversion...\n")
            elif not VALIDATION_AVAILABLE and validate_only:
                print("\n[-] Error: Validation module not available.")
                print("    Install dependencies: pip install -r requirements.txt")
                sys.exit(1)

            success = convert_batch(usfm_file, timing_files, output, combined=combined)
        else:
            print(f"\n[-] Timing file/folder not found: {timing_input}")
            sys.exit(1)

    if success:
        print("\n[*] Done!")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
