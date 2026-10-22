"""The first-run flow, the setup dialog and the shared config of the GUI."""

from typing import ClassVar

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from mktsk import config, gui
from mktsk.gui import MainWindow, first_run
from mktsk.gui.first_run import (
    MissingChoice,
    SetupDialog,
    ask_missing_folder,
    ask_start_setup,
    ensure_base_folder,
    run_setup_dialog,
)


def _unexpected(*args, **kwargs):
    raise AssertionError("a prompt was shown")


def _resolve_sequence(monkeypatch, *results):
    answers = iter(results)
    monkeypatch.setattr(config, "resolve_base_folder", lambda: next(answers))


def _missing(tmp_path):
    return config.BaseFolder(config.BaseFolderState.MISSING, tmp_path / "gone")


def _dialog(qtbot, base, *categories):
    dialog = SetupDialog()
    qtbot.addWidget(dialog)
    dialog.base_input.setText(str(base))
    for field, text in zip(dialog.category_inputs, categories):
        field.setText(text)
    return dialog


def test_ok_returns_the_folder_without_a_prompt(monkeypatch, tmp_path):
    _resolve_sequence(
        monkeypatch, config.BaseFolder(config.BaseFolderState.OK, tmp_path)
    )
    monkeypatch.setattr(first_run, "ask_start_setup", _unexpected)
    monkeypatch.setattr(first_run, "ask_missing_folder", _unexpected)
    monkeypatch.setattr(first_run, "run_setup_dialog", _unexpected)

    assert ensure_base_folder() == tmp_path


def test_declining_the_setup_returns_none(monkeypatch):
    _resolve_sequence(
        monkeypatch, config.BaseFolder(config.BaseFolderState.NOT_CONFIGURED)
    )
    monkeypatch.setattr(first_run, "ask_start_setup", lambda parent=None: False)
    monkeypatch.setattr(first_run, "run_setup_dialog", _unexpected)

    assert ensure_base_folder() is None


def test_the_setup_returns_the_folder_it_saved(monkeypatch, tmp_path):
    _resolve_sequence(
        monkeypatch, config.BaseFolder(config.BaseFolderState.NOT_CONFIGURED)
    )
    monkeypatch.setattr(first_run, "ask_start_setup", lambda parent=None: True)
    monkeypatch.setattr(
        first_run, "run_setup_dialog", lambda parent=None: tmp_path
    )

    assert ensure_base_folder() == tmp_path


def test_a_cancelled_setup_returns_none(monkeypatch):
    _resolve_sequence(
        monkeypatch, config.BaseFolder(config.BaseFolderState.NOT_CONFIGURED)
    )
    monkeypatch.setattr(first_run, "ask_start_setup", lambda parent=None: True)
    monkeypatch.setattr(first_run, "run_setup_dialog", lambda parent=None: None)

    assert ensure_base_folder() is None


def test_cancelling_a_missing_folder_returns_none(monkeypatch, tmp_path):
    _resolve_sequence(monkeypatch, _missing(tmp_path))
    monkeypatch.setattr(
        first_run,
        "ask_missing_folder",
        lambda parent=None, path=None: MissingChoice.CANCEL,
    )

    assert ensure_base_folder() is None


def test_retry_resolves_again_until_the_folder_is_back(monkeypatch, tmp_path):
    gone = _missing(tmp_path)
    back = config.BaseFolder(config.BaseFolderState.OK, tmp_path)
    _resolve_sequence(monkeypatch, gone, back)
    prompts = []
    monkeypatch.setattr(
        first_run,
        "ask_missing_folder",
        lambda parent=None, path=None: (
            prompts.append(path) or MissingChoice.RETRY
        ),
    )

    assert ensure_base_folder() == tmp_path
    assert prompts == [tmp_path / "gone"]


def test_choosing_another_folder_returns_the_new_one(monkeypatch, tmp_path):
    _resolve_sequence(monkeypatch, _missing(tmp_path))
    monkeypatch.setattr(
        first_run,
        "ask_missing_folder",
        lambda parent=None, path=None: MissingChoice.CHOOSE,
    )
    monkeypatch.setattr(
        first_run, "run_setup_dialog", lambda parent=None: tmp_path / "new"
    )

    assert ensure_base_folder() == tmp_path / "new"


def test_a_cancelled_setup_asks_about_the_missing_folder_again(
    monkeypatch, tmp_path
):
    missing = _missing(tmp_path)
    _resolve_sequence(monkeypatch, missing, missing)
    answers = iter([MissingChoice.CHOOSE, MissingChoice.CANCEL])
    asked = []

    def choose(parent=None, path=None):
        asked.append(path)
        return next(answers)

    monkeypatch.setattr(first_run, "ask_missing_folder", choose)
    monkeypatch.setattr(first_run, "run_setup_dialog", lambda parent=None: None)

    assert ensure_base_folder() is None
    assert asked == [tmp_path / "gone", tmp_path / "gone"]


def test_ask_start_setup_returns_the_answer(monkeypatch):
    answers = iter(
        [QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No]
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *args: next(answers))

    assert ask_start_setup() is True
    assert ask_start_setup() is False


class _FakeButton:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class _FakeMessageBox:
    """The slice of `QMessageBox` that the missing-folder prompt uses."""

    class Icon:
        Warning = object()

    class ButtonRole:
        AcceptRole = object()
        RejectRole = object()

    answers: ClassVar[list[str]] = []
    records: ClassVar[list[tuple[str, list[str]]]] = []

    def __init__(self, parent=None):
        self.message = ""
        self.buttons = []
        self.chosen = None

    def setIcon(self, icon):
        self.icon = icon

    def setWindowTitle(self, title):
        self.title = title

    def setText(self, text):
        self.message = text

    def addButton(self, text, role):
        button = _FakeButton(text)
        self.buttons.append(button)
        return button

    def exec(self):
        self.chosen = self.answers.pop(0)
        self.records.append(
            (self.message, [button.text() for button in self.buttons])
        )

    def clickedButton(self):
        return next(
            (button for button in self.buttons if button.text() == self.chosen),
            None,
        )


def test_ask_missing_folder_names_the_path_and_returns_the_button(
    monkeypatch, tmp_path
):
    gone = tmp_path / "gone"
    _FakeMessageBox.answers = ["Retry", "Choose another folder", "Cancel"]
    _FakeMessageBox.records = []
    monkeypatch.setattr(first_run, "QMessageBox", _FakeMessageBox)

    assert ask_missing_folder(None, gone) is MissingChoice.RETRY
    assert ask_missing_folder(None, gone) is MissingChoice.CHOOSE
    assert ask_missing_folder(None, gone) is MissingChoice.CANCEL

    assert _FakeMessageBox.records[0][0] == (
        f"The saved base folder does not exist:\n{gone}"
    )
    assert set(_FakeMessageBox.records[0][1]) == {
        "Retry",
        "Choose another folder",
        "Cancel",
    }


def test_run_setup_dialog_returns_the_saved_folder(monkeypatch, tmp_path):
    class AcceptedDialog:
        def __init__(self, parent=None):
            self.base_folder = tmp_path

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(first_run, "SetupDialog", AcceptedDialog)

    assert run_setup_dialog() == tmp_path


def test_run_setup_dialog_returns_none_when_cancelled(monkeypatch, tmp_path):
    class CancelledDialog:
        def __init__(self, parent=None):
            self.base_folder = tmp_path

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(first_run, "SetupDialog", CancelledDialog)

    assert run_setup_dialog() is None


def test_an_empty_base_folder_shows_the_error(qtbot, tmp_path):
    dialog = _dialog(qtbot, "")
    dialog._accept()

    assert dialog.base_folder is None
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert not dialog.error_label.isHidden()
    assert dialog.error_label.text() == "base folder must not be empty"
    assert not config.config_path().exists()


def test_a_valid_folder_is_created_and_saved(qtbot, tmp_path):
    base = tmp_path / "tasks"
    dialog = _dialog(qtbot, base)
    dialog._accept()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.base_folder == base.resolve()
    assert base.is_dir()
    assert config.load_config() == base.resolve()


@pytest.mark.parametrize("names", [["Able"], ["Able", "Veritas"]])
def test_categories_are_created(qtbot, tmp_path, names):
    base = tmp_path / "tasks"
    dialog = _dialog(qtbot, base, *names)
    dialog._accept()

    for name in names:
        assert (base / name).is_dir()


def test_an_invalid_category_creates_nothing(qtbot, tmp_path):
    base = tmp_path / "tasks"
    dialog = _dialog(qtbot, base, "Foo.")
    dialog._accept()

    assert "dot or a space" in dialog.error_label.text()
    assert not dialog.error_label.isHidden()
    assert not base.exists()
    assert not config.config_path().exists()


def test_only_two_category_fields_exist(qtbot):
    dialog = _dialog(qtbot, "")

    assert len(dialog.category_inputs) == 2


def test_browse_fills_the_line_edit(qtbot, tmp_path, monkeypatch):
    chosen = tmp_path / "chosen"
    starts = []

    def pick(parent, caption, start):
        starts.append(start)
        return str(chosen)

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", pick)
    dialog = _dialog(qtbot, "old")
    dialog.browse()

    assert dialog.base_input.text() == str(chosen)
    assert starts == ["old"]


def test_a_cancelled_browse_keeps_the_text(qtbot, monkeypatch):
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args: ""
    )
    dialog = _dialog(qtbot, "old")
    dialog.browse()

    assert dialog.base_input.text() == "old"


def test_cancel_leaves_the_config_untouched(qtbot, tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    config.save_config(old)
    dialog = _dialog(qtbot, tmp_path / "new", "Able")
    dialog.reject()

    assert dialog.result() == QDialog.DialogCode.Rejected
    assert config.load_config() == old
    assert not (tmp_path / "new").exists()


def test_the_old_folder_is_replaced_only_after_a_successful_ok(
    qtbot, tmp_path
):
    old = tmp_path / "old"
    old.mkdir()
    config.save_config(old)
    base = tmp_path / "new"
    dialog = _dialog(qtbot, base, "Foo.")

    dialog._accept()

    assert config.load_config() == old
    assert not base.exists()

    dialog.category_inputs[0].setText("Able")
    dialog._accept()

    assert config.load_config() == base.resolve()


class _FakeApplication:
    def __init__(self, arguments):
        self.arguments = arguments
        self.executed = False

    def exec(self):
        self.executed = True
        return 7


class _FakeWindow:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.shown = False

    def show(self):
        self.shown = True


def test_startup_exits_one_without_a_base_folder(monkeypatch):
    applications = []

    def application(arguments):
        app = _FakeApplication(arguments)
        applications.append(app)
        return app

    windows = []
    monkeypatch.setattr(gui, "QApplication", application)
    monkeypatch.setattr(gui, "MainWindow", lambda **kwargs: windows.append(kwargs))
    monkeypatch.setattr(gui, "ensure_base_folder", lambda: None)

    assert gui.main() == 1
    assert windows == []
    assert applications[0].executed is False


def test_startup_opens_the_window_on_the_base_folder(monkeypatch, tmp_path):
    windows = []

    def application(arguments):
        return _FakeApplication(arguments)

    def window(**kwargs):
        created = _FakeWindow(**kwargs)
        windows.append(created)
        return created

    monkeypatch.setattr(gui, "QApplication", application)
    monkeypatch.setattr(gui, "MainWindow", window)
    monkeypatch.setattr(gui, "ensure_base_folder", lambda: tmp_path)

    assert gui.main() == 7
    assert windows[0].kwargs == {"base_folder": tmp_path}
    assert windows[0].shown is True


def test_the_window_opens_in_the_folder_it_is_given(qtbot, tmp_path):
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    window = MainWindow(settings=settings, base_folder=tmp_path)
    qtbot.addWidget(window)

    assert window.current_directory == tmp_path.resolve()
