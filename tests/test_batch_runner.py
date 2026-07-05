import pytest
from pathlib import Path
from vidx.batch_runner import BatchRunner, Job
from vidx.config import Config


@pytest.fixture
def sample_workspace(tmp_path):
    usfm = tmp_path / "test.SFM"
    usfm.write_text("\\id MRK\n\\c 1\n\\s1 Title\n\\v 1 Verse one.", encoding="utf-8")
    
    timing = tmp_path / "timing.txt"
    timing.write_text("\\c 1\n\\level phrase\n\\separators .\n0.0\t2.0\ts1\n2.0\t4.0\t1a", encoding="utf-8")
    
    return usfm, timing, tmp_path


def test_add_job():
    runner = BatchRunner()
    job = runner.add_job("a.sfm", "t.txt", "audio.mp3", "out.mp4")
    assert len(runner.jobs) == 1
    assert job.status == "PENDING"
    assert job.usfm_file == "a.sfm"


def test_batch_runner_generate_only_srt(sample_workspace):
    usfm, timing, tmp_dir = sample_workspace
    out_mp4 = tmp_dir / "output.mp4"
    
    config = Config(config_dict={"project": {"generate_only": True, "subtitle_format": "srt"}})
    runner = BatchRunner(config)
    runner.generate_only = True
    runner.subtitle_format = "srt"
    
    job = runner.add_job(str(usfm), str(timing), "dummy_audio.mp3", str(out_mp4))
    res_job = runner._execute_single_job(job)
    
    assert res_job.status == "SUCCESS"
    srt_file = out_mp4.with_suffix(".srt")
    assert srt_file.exists()
    assert "Verse one." in srt_file.read_text(encoding="utf-8")
    # In srt-only mode, ASS should not be generated
    assert not out_mp4.with_suffix(".ass").exists()


def test_batch_runner_generate_only_both(sample_workspace):
    usfm, timing, tmp_dir = sample_workspace
    out_mp4 = tmp_dir / "output.mp4"
    
    config = Config(config_dict={"project": {"generate_only": True, "subtitle_format": "both"}})
    runner = BatchRunner(config)
    runner.generate_only = True
    runner.subtitle_format = "both"
    
    job = runner.add_job(str(usfm), str(timing), "dummy_audio.mp3", str(out_mp4))
    res_job = runner._execute_single_job(job)
    
    assert res_job.status == "SUCCESS"
    assert out_mp4.with_suffix(".srt").exists()
    assert out_mp4.with_suffix(".ass").exists()


def test_batch_runner_missing_input(tmp_path):
    runner = BatchRunner()
    job = runner.add_job(
        str(tmp_path / "non_existent.SFM"),
        str(tmp_path / "non_existent.txt"),
        str(tmp_path / "audio.mp3"),
        str(tmp_path / "out.mp4")
    )
    res_job = runner._execute_single_job(job)
    assert res_job.status == "FAILED"
    assert "USFM file not found" in res_job.error_msg


def test_batch_runner_progress_callback(sample_workspace):
    from unittest.mock import MagicMock
    from vidx.progress import ProgressEvent
    
    usfm, timing, tmp_dir = sample_workspace
    out_mp4 = tmp_dir / "output.mp4"
    
    runner = BatchRunner()
    runner.generate_only = True
    mock_callback = MagicMock()
    runner.progress_reporter.subscribe(mock_callback)
    
    job = runner.add_job(str(usfm), str(timing), "dummy_audio.mp3", str(out_mp4))
    runner._execute_single_job(job)
    
    assert mock_callback.called
    first_event = mock_callback.call_args_list[0][0][0]
    assert isinstance(first_event, ProgressEvent)
    assert first_event.status in ["STARTING", "EXTRACTING_SUBTITLES", "COMPLETED"]


def test_preprocess_background_media_loop_crossfade(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    bg_file = tmp_path / "test_loop.mp4"
    bg_file.write_text("dummy video content")
    
    config = Config(config_dict={
        "video": {"resolution": "1920x1080", "loop_crossfade_sec": 1.5},
        "project": {"output_dir": str(tmp_path / "out")}
    })
    runner = BatchRunner(config)
    runner.add_job("a.sfm", "t.txt", "audio.mp3", "out.mp4", background_media=str(bg_file))
    
    mock_run = MagicMock()
    def side_effect(cmd, **kwargs):
        res = MagicMock()
        res.returncode = 0
        if "ffprobe" in cmd:
            if any("width,height" in arg for arg in cmd):
                res.stdout = "1920x1080\n"
            elif any("format=duration" in arg for arg in cmd):
                res.stdout = "10.0\n"
        elif "ffmpeg" in cmd:
            # Create output file to simulate successful encoding
            out_p = Path(cmd[-1])
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text("cached content")
        return res
    mock_run.side_effect = side_effect
    monkeypatch.setattr("subprocess.run", mock_run)
    
    runner._preprocess_background_media()
    
    # Check that ffmpeg was called with xfade filter
    ffmpeg_calls = [c for c in mock_run.call_args_list if "ffmpeg" in c[0][0]]
    assert len(ffmpeg_calls) == 1
    ff_cmd = ffmpeg_calls[0][0][0]
    assert "-filter_complex" in ff_cmd
    fc_idx = ff_cmd.index("-filter_complex")
    fc_val = ff_cmd[fc_idx + 1]
    assert "xfade=transition=fade:duration=1.5:offset=7.000" in fc_val
    assert "xf1.5s" in runner.jobs[0].background_media


