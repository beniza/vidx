import pytest
from pathlib import Path
from vidx.ffmpeg_builder import FFmpegBuilder


def test_clean_filter_path():
    builder = FFmpegBuilder()
    # Test path format with colons and slashes
    clean = builder._clean_filter_path("C:\\Users\\test\\sub.ass")
    assert "C\\:" in clean
    assert "/" in clean
    assert "\\" not in clean.replace("C\\:", "")


def test_build_command_default_pad():
    config = {
        "video": {"resolution": "1920x1080", "scaling_mode": "pad", "fps": 24},
        "audio": {"codec": "aac", "bitrate": "192k"}
    }
    builder = FFmpegBuilder(config)
    cmd = builder.build_command("audio.mp3", "sub.ass", "out.mp4")
    
    assert "ffmpeg" in cmd
    assert "-y" in cmd
    assert "-shortest" in cmd
    
    # Check scale filter
    vf_idx = cmd.index("-vf")
    vf_chain = cmd[vf_idx + 1]
    assert "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080" in vf_chain
    assert "ass=" in vf_chain


def test_build_command_crop_vertical():
    config = {
        "video": {"resolution": "1080x1920", "scaling_mode": "crop"}
    }
    builder = FFmpegBuilder(config)
    cmd = builder.build_command("audio.mp3", "sub.ass", "vertical.mp4")
    
    vf_idx = cmd.index("-vf")
    vf_chain = cmd[vf_idx + 1]
    assert "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" in vf_chain


def test_build_command_duration_and_lavfi():
    config = {"video": {"resolution": "1080x1080", "fps": 30}}
    builder = FFmpegBuilder(config)
    cmd = builder.build_command("audio.mp3", "sub.ass", "square.mp4", duration=15)
    
    assert "-t" in cmd
    assert cmd[cmd.index("-t") + 1] == "15"
    assert "-shortest" not in cmd
    assert "-f" in cmd
    assert "lavfi" in cmd
    assert "color=c=black:s=1080x1080:r=30" in cmd
