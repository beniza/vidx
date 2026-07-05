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
