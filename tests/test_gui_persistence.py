"""The window and splitter sizes the main window keeps between sessions."""

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from mktsk.gui import MainWindow
from tests.gui_helpers import select_task

_SPLITTER_KEYS = [
    "window/main_splitter",
    "window/directory_splitter",
    "window/table_splitter",
    "window/preview_splitter",
]


def _settings(tmp_path, name="settings.ini"):
    return QSettings(str(tmp_path / name), QSettings.Format.IniFormat)


def _window(qtbot, settings):
    window = MainWindow(settings=settings)
    window.show()
    qtbot.addWidget(window)
    return window


def _sizes(window):
    return {
        "main": window.splitter.sizes(),
        "directory": window.left_splitter.sizes(),
        "table": window.table_splitter.sizes(),
        "preview": window.preview_area.sizes(),
    }


def test_closing_writes_the_geometry_and_every_splitter(qtbot, tmp_path):
    settings = _settings(tmp_path)
    window = _window(qtbot, settings)

    window.close()

    assert settings.contains("window/geometry")
    for key in _SPLITTER_KEYS:
        assert settings.contains(key)


def test_a_new_window_restores_the_saved_size_and_splits(
    qtbot, tmp_path, make_task
):
    settings = _settings(tmp_path)
    file = make_task(tmp_path, "260918", "Foo")
    (file.parent / "notes.txt").write_text("notes", encoding="utf-8")
    first = _window(qtbot, settings)
    first.navigate_to(tmp_path)
    select_task(first, file)
    first.resize(760, 620)
    QApplication.processEvents()
    first.splitter.setSizes([420, 580])
    first.left_splitter.setSizes([500, 200])
    first.table_splitter.setSizes([460, 240])
    first.preview_area.setSizes([600, 300])
    QApplication.processEvents()
    size = first.size()
    sizes = _sizes(first)
    first.close()

    second = _window(qtbot, settings)
    second.navigate_to(tmp_path)
    select_task(second, file)
    QApplication.processEvents()

    assert second.size() == size
    assert _sizes(second) == sizes


def test_an_empty_settings_opens_with_the_defaults(qtbot, tmp_path):
    defaults = _window(qtbot, _settings(tmp_path, "defaults.ini"))
    QApplication.processEvents()
    default_size = defaults.size()
    default_sizes = _sizes(defaults)

    settings = _settings(tmp_path)
    settings.setValue("last_path", str(tmp_path))
    window = _window(qtbot, settings)

    assert window.size() == default_size
    assert _sizes(window) == default_sizes
    assert not window.preview_area.isVisible()


def test_garbage_values_open_with_the_defaults(qtbot, tmp_path):
    defaults = _window(qtbot, _settings(tmp_path, "defaults.ini"))
    QApplication.processEvents()
    default_size = defaults.size()
    default_sizes = _sizes(defaults)

    settings = _settings(tmp_path)
    for key in ["window/geometry", *_SPLITTER_KEYS]:
        settings.setValue(key, b"not a saved state")
    window = _window(qtbot, settings)

    assert window.size() == default_size
    assert _sizes(window) == default_sizes


def test_a_saved_preview_state_keeps_the_details_panel_full_width(
    qtbot, tmp_path, make_task
):
    settings = _settings(tmp_path)
    with_attachment = make_task(tmp_path, "260918", "Foo")
    (with_attachment.parent / "notes.txt").write_text("notes", encoding="utf-8")
    without = make_task(tmp_path, "260919", "Bar")
    first = _window(qtbot, settings)
    first.navigate_to(tmp_path)
    select_task(first, with_attachment)
    first.preview_area.setSizes([200, 600])
    first.close()

    window = _window(qtbot, settings)
    window.navigate_to(tmp_path)
    select_task(window, without)
    QApplication.processEvents()

    assert not window.preview_list_panel.isVisible()
    assert window.preview_area.sizes()[1] == 0
    assert window.preview_text_panel.width() == window.preview_area.width()


def test_a_collapsed_directory_panel_comes_back_with_the_rail(qtbot, tmp_path):
    settings = _settings(tmp_path)
    first = _window(qtbot, settings)
    first.toggle_left_pane()
    first.close()

    window = _window(qtbot, settings)

    assert window.splitter.sizes()[0] == 0
    assert window.toggle_button.toolTip() == "Show panel"
    window.toggle_left_pane()
    assert window.splitter.sizes()[0] > 0
    assert window.toggle_button.toolTip() == "Hide panel"
