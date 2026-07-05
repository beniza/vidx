import pytest
import sys
from unittest.mock import patch
from vidx.cli import main
from vidx import __version__


def test_cli_version(capsys):
    with patch.object(sys, "argv", ["vidx", "--version"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out or __version__ in captured.err


def test_cli_short_version(capsys):
    with patch.object(sys, "argv", ["vidx", "-v"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out or __version__ in captured.err


def test_cli_progress_observer_wiring(tmp_path):
    usfm = tmp_path / "test.SFM"
    usfm.write_text(
        "\\id GEN\n\\c 1\n\\s1 Title\n\\v 1 In beginning.", encoding="utf-8"
    )
    timing = tmp_path / "timing.txt"
    timing.write_text(
        "\\c 1\n\\level phrase\n\\separators .\n0.0\t2.0\ts1\n2.0\t4.0\t1a",
        encoding="utf-8",
    )
    audio = tmp_path / "dummy.mp3"
    audio.write_text("dummy", encoding="utf-8")

    with patch("vidx.progress.TerminalProgressObserver.on_progress") as mock_observer:
        with patch.object(
            sys,
            "argv",
            [
                "vidx",
                "--usfm",
                str(usfm),
                "--timing",
                str(timing),
                "--audio",
                str(audio),
                "--generate-only",
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            assert mock_observer.called


def test_cli_gpu_flag(tmp_path):
    usfm = tmp_path / "test.SFM"
    usfm.write_text(
        "\\id GEN\n\\c 1\n\\s1 Title\n\\v 1 In beginning.", encoding="utf-8"
    )
    timing = tmp_path / "timing.txt"
    timing.write_text(
        "\\c 1\n\\level phrase\n\\separators .\n0.0\t2.0\ts1\n2.0\t4.0\t1a",
        encoding="utf-8",
    )
    audio = tmp_path / "dummy.mp3"
    audio.write_text("dummy", encoding="utf-8")

    with patch("vidx.cli.BatchRunner") as mock_runner_cls:
        mock_runner_cls.return_value.run_all.return_value = {
            "failed": 0,
            "succeeded": 1,
        }
        mock_runner_cls.return_value.jobs = [1]
        with patch.object(
            sys,
            "argv",
            [
                "vidx",
                "--usfm",
                str(usfm),
                "--timing",
                str(timing),
                "--audio",
                str(audio),
                "--gpu",
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            passed_cfg = mock_runner_cls.call_args[1]["config"]
            assert passed_cfg.raw_config["video"]["codec"] == "auto"
