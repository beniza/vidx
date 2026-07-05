import os
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

try:
    import mutagen
except ImportError:
    mutagen = None


@dataclass
class BumperConfig:
    intro_audio: Optional[str] = None
    outro_audio: Optional[str] = None
    title_image: Optional[str] = None
    outro_image: Optional[str] = None
    title_duration: Optional[float] = None
    outro_duration: Optional[float] = None


def get_media_duration(file_path: str) -> float:
    """Get duration of audio or video media file in seconds."""
    path = Path(file_path)
    if not path.exists():
        return 0.0

    # 1. Try mutagen
    if mutagen is not None:
        try:
            audio = mutagen.File(str(path))
            if audio is not None and hasattr(audio, "info") and hasattr(audio.info, "length") and audio.info.length > 0:
                return float(audio.info.length)
        except Exception:
            pass

    # 2. Try ffprobe
    try:
        res = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path)
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        val = res.stdout.strip()
        if val:
            return float(val)
    except Exception:
        pass

    # 3. Try wave module for wav files
    try:
        if path.suffix.lower() == ".wav":
            with wave.open(str(path), "r") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return float(frames) / float(rate)
    except Exception:
        pass

    return 0.0


def prepare_bumper_audio(
    main_audio: str,
    output_audio: str,
    intro_audio: Optional[str] = None,
    outro_audio: Optional[str] = None
) -> Tuple[bool, float, float]:
    """
    Concatenate intro_audio + main_audio + outro_audio into output_audio.
    Returns: (success: bool, intro_duration_sec: float, total_duration_sec: float)
    """
    main_path = Path(main_audio)
    out_path = Path(output_audio)
    
    if not main_path.exists():
        return False, 0.0, 0.0

    intro_path = Path(intro_audio) if intro_audio else None
    outro_path = Path(outro_audio) if outro_audio else None

    has_intro = intro_path is not None and intro_path.exists()
    has_outro = outro_path is not None and outro_path.exists()

    intro_dur = get_media_duration(str(intro_path)) if has_intro else 0.0

    # If no bumpers needed, simply copy or point to main audio
    if not has_intro and not has_outro:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if str(main_path.resolve()) != str(out_path.resolve()):
            shutil.copyfile(str(main_path), str(out_path))
        return True, 0.0, get_media_duration(str(out_path))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build FFmpeg concat command
    inputs = []
    filter_parts = []
    idx = 0

    if has_intro:
        inputs.extend(["-i", str(intro_path)])
        filter_parts.append(f"[{idx}:0]")
        idx += 1

    inputs.extend(["-i", str(main_path)])
    filter_parts.append(f"[{idx}:0]")
    idx += 1

    if has_outro:
        inputs.extend(["-i", str(outro_path)])
        filter_parts.append(f"[{idx}:0]")
        idx += 1

    filter_str = "".join(filter_parts) + f"concat=n={idx}:v=0:a=1[outa]"
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[outa]",
        str(out_path)
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and out_path.exists():
            total_dur = get_media_duration(str(out_path))
            return True, intro_dur, total_dur
        else:
            return False, intro_dur, 0.0
    except Exception:
        return False, intro_dur, 0.0
