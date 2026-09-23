import subprocess

import pytest

from mktsk import helpers


def test_open_file_windows(monkeypatch, tmp_path):
    file = tmp_path / "test.md"
    file.touch()

    called_with = []

    def fake_startfile(path):
        called_with.append(path)

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("os.startfile", fake_startfile)

    helpers.open_file(file)

    assert called_with == [file]

def test_open_file_linux(monkeypatch, tmp_path):
    file = tmp_path / "test.md"
    file.touch()

    called_with = {}

    def fake_run(command, check):
        called_with["command"] = command
        called_with["check"] = check

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("subprocess.run", fake_run)

    helpers.open_file(file)

    assert called_with == {
        "command": ["xdg-open", file],
        "check": True,
    }

def test_open_file_error(monkeypatch, tmp_path):
    file = tmp_path / "test.md"
    file.touch()

    def raise_error(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "xdg-open")

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("subprocess.run", raise_error)

    with pytest.raises(OSError, match="Could not open file"):
        helpers.open_file(file)