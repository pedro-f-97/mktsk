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

def test_readable_title_separates_words():
    assert helpers.readable_title("ItsAlive") == "Its Alive"
    assert helpers.readable_title("FSocietyEverbind") == "F Society Everbind"
    assert helpers.readable_title("Everbind") == "Everbind"
    assert helpers.readable_title("Bigword") == "Bigword"

def test_readable_title_separates_every_capital():
    assert helpers.readable_title("HTMLParser") == "H T M L Parser"
    assert helpers.readable_title("FSociety") == "F Society"

def test_readable_title_starts_a_word_on_a_digit():
    assert helpers.readable_title("Task2") == "Task 2"
    assert helpers.readable_title("FSociety2") == "F Society 2"

def test_readable_title_keeps_consecutive_digits_together():
    assert helpers.readable_title("2026") == "2026"
    assert helpers.readable_title("Q2026") == "Q 2026"

def test_readable_title_empty():
    assert helpers.readable_title("") == ""

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