import subprocess
from pathlib import PurePosixPath

import pytest

from mktsk import helpers
from mktsk.helpers import TaskError


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


@pytest.mark.parametrize("name", ["con.txt", "nul.md", "com1.log", "PRN.json"])
def test_is_reserved_name_with_an_extension(name):
    # Windows reserves the stem, so CON.txt is as refused as a folder called CON
    assert helpers.is_reserved_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "foo:bar",
        "foo?",
        "foo*",
        "foo|",
        "foo<",
        "foo>",
        'foo"bar',
        "a/b",
        "..",
        "foo.",
        "foo ",
        "foo..",
        "foo\tbar",
        "foo\x00bar",
        "C:\\foo",
        "foo\\bar",
        "C:",
    ],
)
def test_validate_name_refuses_what_windows_would(name):
    with pytest.raises(TaskError):
        helpers.validate_name(name)


@pytest.mark.parametrize(
    "name",
    ["Veritas", "my tasks", "Steel Mountain", "260918 - Foo", "Foo-Bar_2"],
)
def test_validate_name_accepts_a_portable_name(name):
    # a task folder carries spaces and a hyphen, and stays valid
    helpers.validate_name(name)


@pytest.mark.parametrize("name", ["", " ", "   "])
def test_validate_name_refuses_an_empty_name(name):
    with pytest.raises(TaskError, match="must not be empty"):
        helpers.validate_name(name)


def test_validate_name_says_when_a_name_is_a_path():
    with pytest.raises(TaskError, match="single path component"):
        helpers.validate_name("foo/bar")


@pytest.mark.parametrize("name", ["C:\\foo", "foo\\bar", "C:"])
def test_validate_name_refuses_a_windows_path_on_any_platform(name, monkeypatch):
    # Path follows the platform we are on, so on Linux it takes "C:\foo" for a
    # single name. Putting the posix flavour on both names is what a Linux run
    # would see, and the answer must not change.
    monkeypatch.setattr(helpers, "Path", PurePosixPath)
    monkeypatch.setattr(helpers, "PureWindowsPath", PurePosixPath)

    with pytest.raises(TaskError):
        helpers.validate_name(name)


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


@pytest.mark.parametrize("kind", ["file", "folder"])
def test_open_file_windows(monkeypatch, tmp_path, kind):
    target = tmp_path / "test.md"
    target.touch()
    if kind == "folder":
        target = tmp_path / "260918 - Foo"
        target.mkdir()

    called_with = []

    def fake_startfile(path):
        called_with.append(path)

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("os.startfile", fake_startfile, raising=False)

    helpers.open_file(target)

    assert called_with == [target]


def test_open_file_linux_uses_xdg_open_when_it_is_there(monkeypatch, tmp_path):
    file = tmp_path / "test.md"
    file.touch()

    called_with = {}

    def fake_run(command, check):
        called_with["command"] = command
        called_with["check"] = check

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/xdg-open")
    monkeypatch.setattr("subprocess.run", fake_run)

    helpers.open_file(file)

    assert called_with == {
        "command": ["xdg-open", file],
        "check": True,
    }


def test_open_file_linux_falls_back_to_gio(monkeypatch, tmp_path):
    file = tmp_path / "test.md"
    file.touch()

    called_with = {}

    def fake_run(command, check):
        called_with["command"] = command
        called_with["check"] = check

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("subprocess.run", fake_run)

    helpers.open_file(file)

    assert called_with == {
        "command": ["gio", "open", file],
        "check": True,
    }


def test_open_file_error(monkeypatch, tmp_path):
    file = tmp_path / "test.md"
    file.touch()

    def raise_error(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "xdg-open")

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/xdg-open")
    monkeypatch.setattr("subprocess.run", raise_error)

    with pytest.raises(OSError, match="Could not open:"):
        helpers.open_file(file)


def test_open_file_error_without_any_opener(monkeypatch, tmp_path):
    file = tmp_path / "test.md"
    file.touch()

    def raise_error(*args, **kwargs):
        raise FileNotFoundError("gio")

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("subprocess.run", raise_error)

    with pytest.raises(OSError, match="Could not open:"):
        helpers.open_file(file)
