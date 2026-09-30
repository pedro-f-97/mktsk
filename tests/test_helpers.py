import subprocess

import pytest

from mktsk import helpers


def test_is_reserved_name_true():
    assert helpers.is_reserved_name("con")
    assert helpers.is_reserved_name("CON")
    assert helpers.is_reserved_name("Prn")
    assert helpers.is_reserved_name("aux")
    assert helpers.is_reserved_name("nul")
    assert helpers.is_reserved_name("com1")
    assert helpers.is_reserved_name("COM9")
    assert helpers.is_reserved_name("lpt1")
    assert helpers.is_reserved_name("LPT9")

def test_is_reserved_name_false():
    assert not helpers.is_reserved_name("conda")
    assert not helpers.is_reserved_name("computer")
    assert not helpers.is_reserved_name("ticket")
    assert not helpers.is_reserved_name("com0")
    assert not helpers.is_reserved_name("com10")
    assert not helpers.is_reserved_name("lpt10")

def test_open_file_windows(monkeypatch, tmp_path):
    file = tmp_path / "test.md"
    file.touch()

    called_with = []

    def fake_startfile(path):
        called_with.append(path)

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("os.startfile", fake_startfile, raising=False)

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