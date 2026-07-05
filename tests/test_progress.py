import pytest
from unittest.mock import MagicMock
from vidx.progress import ProgressEvent, ProgressReporter, parse_ffmpeg_progress_line


def test_progress_event_creation():
    event = ProgressEvent(
        job_id="job_1",
        worker_id=0,
        status="ENCODING_VIDEO",
        percent=45.5,
        book="MRK",
        chapter=1,
        speed="2.3x",
        fps=58.0,
        elapsed_sec=12.0,
        eta_sec=14.5,
        message="Encoding chapter 1",
    )
    assert event.job_id == "job_1"
    assert event.worker_id == 0
    assert event.status == "ENCODING_VIDEO"
    assert event.percent == 45.5
    assert event.book == "MRK"
    assert event.chapter == 1
    assert event.speed == "2.3x"
    assert event.fps == 58.0
    assert event.elapsed_sec == 12.0
    assert event.eta_sec == 14.5


def test_parse_ffmpeg_progress_line():
    line = "frame= 120 fps= 24.5 q=0.0 size= 1024kB time=00:00:05.00 bitrate=1677.7kbits/s speed= 2.0x"
    total_duration_sec = 20.0

    event_data = parse_ffmpeg_progress_line(line, total_duration_sec=total_duration_sec)
    assert event_data is not None
    assert event_data["elapsed_sec"] == 5.0
    assert event_data["fps"] == 24.5
    assert event_data["speed"] == "2.0x"
    assert event_data["percent"] == 25.0  # 5.0 / 20.0 * 100
    assert event_data["eta_sec"] == 7.5  # (20.0 - 5.0) / 2.0 speed


def test_progress_reporter_dispatch():
    reporter = ProgressReporter()
    mock_gui_callback = MagicMock()
    mock_cli_callback = MagicMock()

    reporter.subscribe(mock_gui_callback)
    reporter.subscribe(mock_cli_callback)

    event = ProgressEvent(
        job_id="test_job", worker_id=1, status="COMPLETED", percent=100.0
    )
    reporter.emit(event)

    mock_gui_callback.assert_called_once_with(event)
    mock_cli_callback.assert_called_once_with(event)


def test_terminal_progress_observer():
    from vidx.progress import TerminalProgressObserver

    observer = TerminalProgressObserver(total_jobs=10, use_rich=False)

    event = ProgressEvent(
        job_id="job_1",
        worker_id=1,
        status="ENCODING_VIDEO",
        percent=50.0,
        book="MAT",
        chapter=1,
        speed="2.5x",
        fps=60.0,
    )
    # Calling on_progress should cleanly handle updates in fallback or rich mode
    observer.on_progress(event)
    assert 1 in observer.worker_tasks or observer.last_event == event
