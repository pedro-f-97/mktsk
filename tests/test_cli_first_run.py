import io
from pathlib import Path

import pytest
from freezegun import freeze_time

import mktsk.main as cli
from mktsk import config


@pytest.fixture
def config_file(monkeypatch, tmp_path):
    target = tmp_path / "config" / "config.json"
    monkeypatch.setattr(config, "config_path", lambda: target)
    monkeypatch.setattr(config, "_read_last_path", lambda: None)
    return target


def _scripted(*answers):
    iterator = iter(answers)

    def read(_prompt):
        return next(iterator)

    return read


def _interactive(monkeypatch):
    monkeypatch.setattr(cli, "_interactive", lambda: True)


def _not_interactive(monkeypatch):
    monkeypatch.setattr(cli, "_interactive", lambda: False)


def test_interactive_needs_both_streams(monkeypatch):
    class Stream:
        def __init__(self, is_tty):
            self.is_tty = is_tty

        def isatty(self):
            return self.is_tty

    monkeypatch.setattr(cli.sys, "stdin", Stream(True))
    monkeypatch.setattr(cli.sys, "stdout", Stream(True))
    assert cli._interactive() is True

    monkeypatch.setattr(cli.sys, "stdout", Stream(False))
    assert cli._interactive() is False


@freeze_time("2026-09-22")
def test_not_configured_then_setup_then_the_command_runs(
    monkeypatch, tmp_path, config_file
):
    base = tmp_path / "tasks"
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo"])
    opened = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened.append)
    output = io.StringIO()

    result = cli.main(input_fn=_scripted("", str(base), ""), output=output)

    file = base / "260922 - Foo" / "Foo.md"
    assert result == 0
    assert file.is_file()
    assert opened == [file]
    assert config.load_config(config_file) == base.resolve()
    assert output.getvalue().startswith(
        "mktsk is not configured yet. Start setup? [Y/n] "
    )
    assert "Base folder: " in output.getvalue()
    assert "Category (optional): " in output.getvalue()


def test_declining_the_setup_exits_one(monkeypatch, tmp_path, config_file):
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo"])
    output = io.StringIO()

    result = cli.main(input_fn=_scripted("n"), output=output)

    assert result == 1
    assert not config_file.exists()
    assert not (tmp_path / "tasks").exists()
    assert "Start setup?" in output.getvalue()


def test_missing_then_retry_continues(monkeypatch, tmp_path, config_file):
    missing = tmp_path / "gone"
    config.save_config(missing, config_file)
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])
    output = io.StringIO()

    def retry(_prompt):
        missing.mkdir()
        return "r"

    result = cli.main(input_fn=retry, output=output)

    assert result == 0
    assert missing.is_dir()
    assert f"The saved base folder does not exist: {missing}" in output.getvalue()
    assert config.load_config(config_file) == missing


@freeze_time("2026-09-22")
def test_missing_then_choose_another_folder(monkeypatch, tmp_path, config_file):
    missing = tmp_path / "gone"
    base = tmp_path / "tasks"
    config.save_config(missing, config_file)
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo"])
    opened = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened.append)
    output = io.StringIO()

    result = cli.main(input_fn=_scripted("c", str(base), ""), output=output)

    assert result == 0
    assert (base / "260922 - Foo" / "Foo.md").is_file()
    assert config.load_config(config_file) == base.resolve()
    assert f"The saved base folder does not exist: {missing}" in output.getvalue()
    assert opened == [base / "260922 - Foo" / "Foo.md"]


def test_missing_then_quit_exits_one(monkeypatch, tmp_path, config_file):
    missing = tmp_path / "gone"
    config.save_config(missing, config_file)
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo"])
    output = io.StringIO()

    result = cli.main(input_fn=_scripted("x", "q"), output=output)

    assert result == 1
    assert not missing.exists()
    assert config.load_config(config_file) == missing
    assert output.getvalue().count("[r]etry, [c]hoose another folder, [q]uit?") == 2


def test_an_invalid_base_folder_is_asked_again(monkeypatch, tmp_path, config_file):
    base = tmp_path / "tasks"
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])
    output = io.StringIO()

    result = cli.main(input_fn=_scripted("", "", "\0", str(base), ""), output=output)

    assert result == 0
    assert "Error: base folder must not be empty" in output.getvalue()
    assert "is not a usable folder" in output.getvalue()
    assert config.load_config(config_file) == base.resolve()


def test_a_base_folder_that_cannot_be_resolved_is_refused(monkeypatch):
    def fail_resolve(self):
        raise OSError("cannot resolve")

    monkeypatch.setattr(Path, "resolve", fail_resolve)

    assert cli._valid_base_folder("relative") is None


def test_setup_takes_two_categories(monkeypatch, tmp_path, config_file):
    base = tmp_path / "tasks"
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])
    output = io.StringIO()

    result = cli.main(
        input_fn=_scripted("", str(base), "Able", "Veritas"), output=output
    )

    assert result == 0
    assert (base / "Able").is_dir()
    assert (base / "Veritas").is_dir()
    assert config.load_config(config_file) == base.resolve()


def test_an_invalid_category_is_asked_again(monkeypatch, tmp_path, config_file):
    base = tmp_path / "tasks"
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "--list"])
    output = io.StringIO()

    result = cli.main(input_fn=_scripted("", str(base), "Foo.", ""), output=output)

    assert result == 0
    assert "Error: category name must not end in a dot or a space" in output.getvalue()
    assert not (base / "Foo.").exists()
    assert config.load_config(config_file) == base.resolve()


def test_a_failed_setup_reports_the_error(monkeypatch, tmp_path, config_file):
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo"])
    output = io.StringIO()

    def fail_setup(*args, **kwargs):
        raise OSError("cannot create")

    monkeypatch.setattr(config, "run_setup", fail_setup)

    result = cli.main(input_fn=_scripted("", str(tmp_path / "tasks"), ""), output=output)

    assert result == 1
    assert "Error: cannot create" in output.getvalue()
    assert not config_file.exists()


@freeze_time("2026-09-22")
def test_an_explicit_folder_skips_the_first_run_routine(monkeypatch, tmp_path, config_file):
    base = tmp_path / "elsewhere"
    monkeypatch.chdir(tmp_path)
    _interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "--folder", str(base), "Foo"])
    opened = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened.append)
    output = io.StringIO()

    def must_not_ask(_prompt):
        raise AssertionError("the first-run routine was asked")

    result = cli.main(input_fn=must_not_ask, output=output)

    assert result == 0
    assert (base / "260922 - Foo" / "Foo.md").is_file()
    assert not config_file.exists()
    assert output.getvalue() == ""


def test_not_configured_without_a_terminal_exits_three(
    monkeypatch, tmp_path, config_file, capsys
):
    monkeypatch.chdir(tmp_path)
    _not_interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo"])
    output = io.StringIO()

    def must_not_ask(_prompt):
        raise AssertionError("a prompt was shown")

    result = cli.main(input_fn=must_not_ask, output=output)

    assert result == 3
    assert output.getvalue() == ""
    assert capsys.readouterr().err == (
        "mktsk is not configured: no base folder saved. "
        "Run it from a terminal to set it up.\n"
    )
    assert not config_file.exists()


def test_missing_without_a_terminal_exits_three_and_names_the_path(
    monkeypatch, tmp_path, config_file, capsys
):
    missing = tmp_path / "gone"
    config.save_config(missing, config_file)
    monkeypatch.chdir(tmp_path)
    _not_interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo"])
    output = io.StringIO()

    result = cli.main(input_fn=lambda _prompt: "q", output=output)

    assert result == 3
    assert output.getvalue() == ""
    assert capsys.readouterr().err == (
        "mktsk is not configured: the saved base folder does not exist: "
        f"{missing}. Run it from a terminal to set it up.\n"
    )


@freeze_time("2026-09-22")
def test_a_configured_folder_is_used_from_any_directory(
    monkeypatch, tmp_path, config_file
):
    base = tmp_path / "tasks"
    base.mkdir()
    config.save_config(base, config_file)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    _not_interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "Foo"])
    opened = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened.append)

    result = cli.main()

    assert result == 0
    assert (base / "260922 - Foo" / "Foo.md").is_file()
    assert opened == [base / "260922 - Foo" / "Foo.md"]


@freeze_time("2026-09-22")
def test_an_explicit_folder_works_without_a_terminal(
    monkeypatch, tmp_path, config_file
):
    base = tmp_path / "elsewhere"
    monkeypatch.chdir(tmp_path)
    _not_interactive(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mktsk", "--folder", str(base), "Foo"])
    opened = []
    monkeypatch.setattr("mktsk.helpers.open_file", opened.append)

    result = cli.main()

    assert result == 0
    assert (base / "260922 - Foo" / "Foo.md").is_file()
    assert not config_file.exists()
