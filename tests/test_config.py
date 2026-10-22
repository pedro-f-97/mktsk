import builtins
import json
import sys
import types
from pathlib import Path

import pytest

from mktsk import config
from mktsk.config import (
    BaseFolder,
    BaseFolderState,
    config_path,
    load_config,
    migrate_from_qsettings,
    resolve_base_folder,
    run_setup,
    save_config,
    validate_category,
)


@pytest.fixture
def config_file(tmp_path):
    return tmp_path / "config" / "config.json"


def _write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _fake_qt(monkeypatch, value):
    calls = []

    class FakeSettings:
        def __init__(self, organization, application):
            calls.append((organization, application))

        def value(self, key):
            calls.append(key)
            return value

    module = types.ModuleType("PySide6.QtCore")
    module.QSettings = FakeSettings
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", module)

    return calls


def test_windows_config_lives_in_appdata():
    env = {"APPDATA": "C:/Users/me/AppData/Roaming", "HOME": "/home/me"}

    assert config_path(env, "win32") == Path(env["APPDATA"]) / "mktsk" / "config.json"


def test_windows_without_appdata_falls_back_to_the_home_folder():
    assert config_path({"HOME": "/home/me"}, "win32") == Path(
        "/home/me/AppData/Roaming/mktsk/config.json"
    )


def test_linux_config_lives_in_xdg_config_home():
    assert config_path({"XDG_CONFIG_HOME": "/home/me/.config-xdg"}, "linux") == Path(
        "/home/me/.config-xdg/mktsk/config.json"
    )


def test_linux_without_xdg_config_home_uses_dot_config():
    assert config_path({"HOME": "/home/me"}, "linux") == Path(
        "/home/me/.config/mktsk/config.json"
    )


def test_without_a_home_the_system_home_is_used(monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: Path("/system/home"))

    assert config_path({}, "linux") == Path("/system/home/.config/mktsk/config.json")


def test_macos_config_lives_in_application_support():
    assert config_path({"HOME": "/Users/me"}, "darwin") == Path(
        "/Users/me/Library/Application Support/mktsk/config.json"
    )


def test_the_default_config_path_is_built_from_the_running_environment():
    assert config_path().name == "config.json"
    assert config_path().parent.name == "mktsk"


def test_a_missing_config_holds_no_folder(tmp_path):
    assert load_config(tmp_path / "missing.json") is None


def test_a_corrupt_config_holds_no_folder(tmp_path):
    target = tmp_path / "config.json"
    target.write_text("{not json", encoding="utf-8")

    assert load_config(target) is None


def test_a_config_that_is_not_an_object_holds_no_folder(tmp_path):
    target = _write(tmp_path / "config.json", ["/tasks"])

    assert load_config(target) is None


@pytest.mark.parametrize("value", ["", "   ", 5, None])
def test_a_config_without_a_usable_folder_holds_none(tmp_path, value):
    target = _write(tmp_path / "config.json", {"base_folder": value})

    assert load_config(target) is None


def test_a_valid_config_holds_its_folder(tmp_path):
    target = _write(tmp_path / "config.json", {"base_folder": "/tasks"})

    assert load_config(target) == Path("/tasks")


def test_saving_creates_the_config_folder_and_writes_json(tmp_path, config_file):
    save_config(tmp_path / "tasks", config_file)

    assert config_file.parent.is_dir()
    assert json.loads(config_file.read_text(encoding="utf-8")) == {
        "base_folder": str(tmp_path / "tasks")
    }


def test_saving_again_replaces_the_folder_and_keeps_valid_json(tmp_path, config_file):
    save_config(tmp_path / "one", config_file)
    save_config(tmp_path / "two", config_file)

    assert load_config(config_file) == tmp_path / "two"


def test_saving_leaves_no_temporary_file_behind(tmp_path, config_file):
    save_config(tmp_path / "tasks", config_file)

    assert list(config_file.parent.iterdir()) == [config_file]


def test_a_failed_save_removes_the_temporary_file(monkeypatch, tmp_path, config_file):
    def fail_replace(*args):
        raise OSError("cannot replace")

    monkeypatch.setattr(config.os, "replace", fail_replace)

    with pytest.raises(OSError):
        save_config(tmp_path / "tasks", config_file)

    assert not config_file.exists()
    assert list(config_file.parent.iterdir()) == []


def test_migration_writes_the_folder_the_gui_saved(monkeypatch, tmp_path, config_file):
    folder = tmp_path / "tasks"
    folder.mkdir()
    calls = _fake_qt(monkeypatch, str(folder))

    migrated = migrate_from_qsettings(config_file)

    assert migrated == folder
    assert load_config(config_file) == folder
    assert calls == [("mktsk", "mktsk"), "last_path"]


def test_migration_keeps_a_folder_that_no_longer_exists(
    monkeypatch, tmp_path, config_file
):
    folder = tmp_path / "gone"
    _fake_qt(monkeypatch, str(folder))

    migrated = migrate_from_qsettings(config_file)

    assert migrated == folder
    assert load_config(config_file) == folder


def test_migration_does_nothing_without_pyside6(
    monkeypatch, tmp_path, config_file, capsys
):
    real_import = builtins.__import__

    def import_without_qt(name, *args, **kwargs):
        if name.startswith("PySide6"):
            raise ImportError("no PySide6 here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_qt)

    assert migrate_from_qsettings(config_file) is None
    assert not config_file.exists()


def test_migration_does_nothing_with_an_empty_value(monkeypatch, tmp_path, config_file):
    _fake_qt(monkeypatch, "")

    assert migrate_from_qsettings(config_file) is None
    assert not config_file.exists()


def test_migration_does_nothing_with_a_value_that_is_not_a_string(
    monkeypatch, tmp_path, config_file
):
    _fake_qt(monkeypatch, 5)

    assert migrate_from_qsettings(config_file) is None
    assert not config_file.exists()


def test_migration_does_not_read_qsettings_when_the_config_is_there(
    monkeypatch, config_file
):
    config_file.parent.mkdir(parents=True)
    config_file.write_text('{"base_folder": "/kept"}', encoding="utf-8")

    def must_not_run():
        raise AssertionError("QSettings was read")

    monkeypatch.setattr(config, "_read_last_path", must_not_run)

    assert migrate_from_qsettings(config_file) is None
    assert load_config(config_file) == Path("/kept")


def test_migration_never_writes_the_old_settings_back(monkeypatch, tmp_path, config_file):
    folder = tmp_path / "tasks"
    calls = _fake_qt(monkeypatch, str(folder))

    migrate_from_qsettings(config_file)

    # only the constructor and one read, never a setter
    assert calls == [("mktsk", "mktsk"), "last_path"]


def test_resolve_reports_a_usable_folder(tmp_path, config_file):
    _write(config_file, {"base_folder": str(tmp_path)})

    assert resolve_base_folder(config_file) == BaseFolder(
        BaseFolderState.OK, tmp_path
    )


def test_resolve_reports_when_nothing_is_saved(monkeypatch, config_file):
    monkeypatch.setattr(config, "_read_last_path", lambda: None)

    assert resolve_base_folder(config_file) == BaseFolder(
        BaseFolderState.NOT_CONFIGURED
    )


def test_resolve_migrates_before_reading_a_missing_config(
    monkeypatch, tmp_path, config_file
):
    folder = tmp_path / "tasks"
    folder.mkdir()
    _fake_qt(monkeypatch, str(folder))

    assert resolve_base_folder(config_file) == BaseFolder(BaseFolderState.OK, folder)


def test_resolve_reports_a_saved_folder_that_is_gone(tmp_path, config_file):
    gone = tmp_path / "gone"
    _write(config_file, {"base_folder": str(gone)})

    assert resolve_base_folder(config_file) == BaseFolder(
        BaseFolderState.MISSING, gone
    )


def test_a_valid_category_is_cleaned():
    assert validate_category("  Veritas  ") == "Veritas"


@pytest.mark.parametrize("name", ["", "   "])
def test_an_empty_category_is_refused(name):
    with pytest.raises(ValueError, match="empty"):
        validate_category(name)


@pytest.mark.parametrize("name", ["a/b", "a\\b", "a:b", "a*b", "a?b", "a|b"])
def test_a_category_with_an_invalid_character_is_refused(name):
    with pytest.raises(ValueError, match="Windows"):
        validate_category(name)


def test_a_category_with_a_control_character_is_refused():
    with pytest.raises(ValueError, match="Windows"):
        validate_category("a\x01b")


@pytest.mark.parametrize("name", ["con", "CON.txt"])
def test_a_reserved_category_is_refused(name):
    with pytest.raises(ValueError, match="reserved"):
        validate_category(name)


@pytest.mark.parametrize("name", [".hidden", "_work"])
def test_a_hidden_category_is_refused(name):
    with pytest.raises(ValueError, match="dot or an underscore"):
        validate_category(name)


def test_a_category_that_looks_like_a_task_is_refused():
    with pytest.raises(ValueError, match="look like a task"):
        validate_category("260918 - Foo")


def test_a_category_that_looks_like_a_reserved_task_is_refused():
    with pytest.raises(ValueError, match="look like a task"):
        validate_category("260918 - CON")


@pytest.mark.parametrize("name", ["Foo.", "Foo. "])
def test_a_category_ending_in_a_dot_or_a_space_is_refused(name):
    with pytest.raises(ValueError, match="dot or a space"):
        validate_category(name)


def test_a_category_that_repeats_another_ignoring_the_case_is_refused():
    with pytest.raises(ValueError, match="already a category"):
        validate_category("Veritas", ["veritas"])


def test_a_category_that_does_not_repeat_another_is_taken():
    assert validate_category("Able", ["Veritas"]) == "Able"


def test_setup_without_categories_creates_the_base_folder(tmp_path, config_file):
    folder = run_setup(tmp_path / "tasks", [], config_path=config_file)

    assert folder == (tmp_path / "tasks").resolve()
    assert folder.is_dir()
    assert load_config(config_file) == folder


def test_setup_creates_one_category(tmp_path, config_file):
    folder = run_setup(tmp_path / "tasks", ["Veritas"], config_path=config_file)

    assert (folder / "Veritas").is_dir()


def test_setup_creates_two_categories(tmp_path, config_file):
    folder = run_setup(
        tmp_path / "tasks", ["Veritas", "Able"], config_path=config_file
    )

    assert (folder / "Veritas").is_dir()
    assert (folder / "Able").is_dir()


def test_setup_accepts_folders_that_are_already_there(tmp_path, config_file):
    base = tmp_path / "tasks"
    (base / "Veritas").mkdir(parents=True)

    folder = run_setup(base, ["Veritas"], config_path=config_file)

    assert folder == base.resolve()
    assert (folder / "Veritas").is_dir()


def test_setup_refuses_more_than_two_categories(tmp_path, config_file):
    with pytest.raises(ValueError, match="at most 2"):
        run_setup(tmp_path / "tasks", ["A", "B", "C"], config_path=config_file)

    assert not (tmp_path / "tasks").exists()
    assert not config_file.exists()


def test_setup_refuses_an_empty_base_folder(config_file):
    with pytest.raises(ValueError, match="must not be empty"):
        run_setup("   ", [], config_path=config_file)

    assert not config_file.exists()


def test_an_invalid_category_leaves_the_old_config_and_creates_nothing(
    tmp_path, config_file
):
    save_config(tmp_path / "old", config_file)

    with pytest.raises(ValueError):
        run_setup(tmp_path / "new", ["Foo."], config_path=config_file)

    assert load_config(config_file) == tmp_path / "old"
    assert not (tmp_path / "new").exists()


def test_a_failed_folder_creation_leaves_the_old_config(monkeypatch, tmp_path, config_file):
    save_config(tmp_path / "old", config_file)

    def fail_mkdir(*args, **kwargs):
        raise OSError("cannot create")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    with pytest.raises(OSError):
        run_setup(tmp_path / "new", [], config_path=config_file)

    assert load_config(config_file) == tmp_path / "old"


def test_setup_replaces_the_old_folder_only_after_success(tmp_path, config_file):
    save_config(tmp_path / "old", config_file)

    folder = run_setup(tmp_path / "new", ["Veritas"], config_path=config_file)

    assert load_config(config_file) == folder
    assert load_config(config_file) != tmp_path / "old"
