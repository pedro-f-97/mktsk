import shutil

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor

from mktsk import gui
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

    assert module.main is gui_main


def test_rows_are_tall_enough_for_the_action_bar(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    listing = task_listing(window)
    listing.setCurrentItem(listing.item(0))

    assert listing.visualItemRect(listing.item(0)).height() >= (
        listing.action_bar.sizeHint().height()
    )


def _ink(draw):
    """Renders an icon and returns its ink, one cell per logical pixel."""
    icon = gui._stroked_icon(QColor("#000000"), draw)
    image = icon.pixmap(QSize(gui._ICON_SIZE, gui._ICON_SIZE)).toImage()
    step = image.width() / image.deviceIndependentSize().width()
    return [
        [
            image.pixelColor(round(x * step), round(y * step)).alpha() > 0
            for x in range(gui._ICON_SIZE)
        ]
        for y in range(gui._ICON_SIZE)
    ]


def _painted(ink, along, at):
    """Whether a line of the icon has ink, across a row or a column."""
    if along == "column":
        return any(ink[y][at] for y in range(gui._ICON_SIZE))
    return any(ink[at])


def test_the_folder_outline_is_closed(qapp):
    ink = _ink(gui._draw_folder)

    # every side of a closed folder is drawn, the left one like the right one
    assert _painted(ink, "column", 1) is True
    assert _painted(ink, "column", 16) is True
    assert _painted(ink, "row", 15) is True

    # and it is an outline, not a filled block
    assert ink[11][8] is False


def test_the_folder_has_a_tab_and_not_just_a_box(qapp):
    ink = _ink(gui._draw_folder)

    # the tab stands above the body, so the top is inked on the left only
    assert ink[4][5] is True
    assert ink[4][12] is False
    assert ink[6][12] is True


def test_the_plus_is_symmetric_about_its_centre(qapp):
    ink = _ink(gui._draw_plus)
    last = gui._ICON_SIZE - 1
    centre = gui._ICON_SIZE // 2

    # the bars cross at the middle of the icon, and reach as far either side
    assert ink[centre][centre] is True
    for offset in range(gui._ICON_SIZE):
        assert ink[centre][offset] == ink[centre][last - offset]
        assert ink[offset][centre] == ink[last - offset][centre]
