import pytest
from pathlib import Path
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


def test_cli_manifest_flag(tmp_path):
    manifest_file = tmp_path / "publish_manifest.json"
    manifest_file.write_text("[]", encoding="utf-8")

    with patch("vidx.cli.run_publisher") as mock_pub:
        with patch.object(sys, "argv", ["vidx", "--manifest", str(manifest_file)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            mock_pub.assert_called_once_with(str(manifest_file), config=None)


def test_run_publisher_defaults_token_file_next_to_manifest(tmp_path):
    from vidx.cli import run_publisher

    manifest_file = tmp_path / "publish_manifest.json"
    manifest_file.write_text(
        '{"entries": [{"id": "1", "video_path": "v.mp4", "thumbnail_path": null, '
        '"book": "LUK", "chapter": 1, "language": "snd", "title": "t", "description": "d", '
        '"privacy_status": "unlisted", "category_id": "22", "playlist_name": "", "tags": [], '
        '"status": "PENDING"}]}',
        encoding="utf-8",
    )

    with patch("vidx.cli.YouTubePublisher") as mock_pub_cls:
        mock_pub_cls.return_value.publish_entry.return_value = "yt-id"
        run_publisher(str(manifest_file))

    _, kwargs = mock_pub_cls.call_args
    assert kwargs["token_file"] == str(manifest_file.parent / "youtube_token.json")


def test_run_publisher_honors_config_token_file_override(tmp_path):
    from vidx.cli import run_publisher
    from vidx.config import Config

    manifest_file = tmp_path / "publish_manifest.json"
    manifest_file.write_text(
        '{"entries": [{"id": "1", "video_path": "v.mp4", "thumbnail_path": null, '
        '"book": "LUK", "chapter": 1, "language": "snd", "title": "t", "description": "d", '
        '"privacy_status": "unlisted", "category_id": "22", "playlist_name": "", "tags": [], '
        '"status": "PENDING"}]}',
        encoding="utf-8",
    )

    config = Config()
    config.raw_config["publishing"]["token_file"] = "~/.vidx/custom_token.json"

    with patch("vidx.cli.YouTubePublisher") as mock_pub_cls:
        mock_pub_cls.return_value.publish_entry.return_value = "yt-id"
        run_publisher(str(manifest_file), config=config)

    _, kwargs = mock_pub_cls.call_args
    assert kwargs["token_file"] == "~/.vidx/custom_token.json"


def test_tag_test_duration_marks_test_renders():
    """A -t render must be distinguishable from a final by filename alone."""
    from vidx.cli import tag_test_duration

    # whole seconds lose the .0
    assert tag_test_duration("out/Mark_01.mp4", 25.0) == str(
        Path("out/Mark_01_25s.mp4")
    )
    # fractional durations keep their decimal
    assert tag_test_duration("out/Mark_01.mp4", 7.5) == str(
        Path("out/Mark_01_7.5s.mp4")
    )
    # idempotent: re-running the same -t never stacks a second suffix
    once = tag_test_duration("out/Mark_01.mp4", 25)
    assert tag_test_duration(once, 25) == once
    # a different -t value on an already-tagged name is still distinguishable
    assert tag_test_duration(once, 15).endswith("_25s_15s.mp4")
