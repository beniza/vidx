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


def test_render_with_progress_callback():
    from unittest.mock import patch, MagicMock
    from vidx.progress import ProgressEvent
    
    builder = FFmpegBuilder({"video": {"resolution": "1920x1080"}})
    mock_callback = MagicMock()
    
    mock_process = MagicMock()
    mock_stdout = MagicMock()
    lines = iter([
        "frame= 10 fps= 24 q=0.0 size= 100kB time=00:00:01.00 bitrate=800.0kbits/s speed= 1.0x\n",
        "frame= 20 fps= 24 q=0.0 size= 200kB time=00:00:02.00 bitrate=800.0kbits/s speed= 1.0x\n",
        ""
    ])
    mock_stdout.readline.side_effect = lambda: next(lines, "")
    mock_process.stdout = mock_stdout
    mock_process.poll.return_value = 0
    mock_process.returncode = 0
    
    with patch("subprocess.Popen", return_value=mock_process):
        success, msg = builder.render(
            "audio.mp3", "sub.ass", "out.mp4", duration=10.0,
            progress_callback=mock_callback, job_id="job_1", worker_id=1, book="GEN", chapter=1
        )
        
    assert success is True
    assert mock_callback.call_count >= 3  # Start, 2 progress lines, Completed
    encoding_event = mock_callback.call_args_list[-2][0][0]
    assert isinstance(encoding_event, ProgressEvent)
    assert encoding_event.percent == 20.0  # 2.0 sec out of 10.0 sec
    assert encoding_event.book == "GEN"
    assert encoding_event.chapter == 1
    
    final_event = mock_callback.call_args_list[-1][0][0]
    assert final_event.status == "COMPLETED"
    assert final_event.percent == 100.0

