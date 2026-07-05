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
