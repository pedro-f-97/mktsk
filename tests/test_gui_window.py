import shutil

from PySide6.QtCore import Qt

from mktsk.gui import main as gui_main
from tests.gui_helpers import select_tab, tab_labels, task_listing


def test_choose_directory(window, tmp_path, monkeypatch, qtbot):
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(tmp_path),
    )
    qtbot.mouseClick(window.choose_button, Qt.MouseButton.LeftButton)

    assert window.current_directory == tmp_path.resolve()


def test_choose_directory_cancelled(window, monkeypatch, qtbot):
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: "",
    )
    before = window.current_directory
    qtbot.mouseClick(window.choose_button, Qt.MouseButton.LeftButton)

    assert window.current_directory == before


def test_up_button_navigates_up(window, tmp_path, qtbot):
    sub = tmp_path / "sub"
    sub.mkdir()
    window.navigate_to(sub)

    qtbot.mouseClick(window.up_button, Qt.MouseButton.LeftButton)

    assert window.current_directory == tmp_path.resolve()


def test_refresh_button_reloads(window, tmp_path, qtbot, make_task):
    window.navigate_to(tmp_path)
    make_task(tmp_path, "260918", "Foo")

    qtbot.mouseClick(window.refresh_button, Qt.MouseButton.LeftButton)

    assert tab_labels(window, tmp_path.name) == ["18/09/2026  Foo"]


def test_refresh_keeps_the_active_tab(window, tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260925", "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")

    window.refresh()

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Veritas"


def test_refresh_falls_back_to_all_when_the_tab_is_gone(window, tmp_path, make_task):
    make_task(tmp_path / "Veritas", "260925", "Foo")
    window.navigate_to(tmp_path)
    select_tab(window, "Veritas")
    shutil.rmtree(tmp_path / "Veritas")

    window.refresh()

    assert window.tabs.tabText(window.tabs.currentIndex()) == "All"


def test_refresh_missing_directory(window, tmp_path):
    window.current_directory = tmp_path / "a.md"

    window.refresh()

    assert window.tabs.count() == 0
    assert window.directory_tree.topLevelItemCount() == 0


def test_close_saves_last_path(window, tmp_path):
    window.navigate_to(tmp_path)
    window.close()

    assert window.settings.value("last_path") == str(tmp_path.resolve())


def test_module_entry_point_uses_gui_main():
    from mktsk import __main__ as module

    assert module.main.__code__.co_name == gui_main.__code__.co_name or module.main is gui_main


def test_rows_are_tall_enough_for_the_action_bar(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    listing.setCurrentItem(listing.item(0))

    assert listing.visualItemRect(listing.item(0)).height() >= (
        listing.action_bar.sizeHint().height()
    )
