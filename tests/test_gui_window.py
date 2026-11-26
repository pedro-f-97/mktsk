import shutil
from unittest.mock import Mock

from PySide6.QtCore import QEvent, QMargins, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel

from mktsk.gui import main as gui_main
from mktsk.gui.tray import TrayController
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


def test_close_leaves_no_last_path(window, tmp_path):
    window.navigate_to(tmp_path)
    window.close()

    assert not window.settings.contains("last_path")


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


def test_central_widget_is_container_above_splitter(window):
    central = window.centralWidget()
    assert central is not window.splitter
    assert window.splitter.parent() is central


def test_central_layout_holds_title_bar_and_splitter(window):
    container = window.centralWidget()
    layout = container.layout()
    assert layout is not None
    first = layout.itemAt(0)
    assert first is not None
    assert first.widget() is window.title_bar
    second = layout.itemAt(1)
    assert second is not None
    assert second.widget() is window.splitter
    assert layout.contentsMargins() == QMargins(0, 0, 0, 0)
    assert layout.spacing() == 0


def test_title_bar_sits_right_above_splitter(window):
    assert window.title_bar.geometry().bottom() + 1 == window.splitter.geometry().top()


def test_title_bar_title_shows_window_title(window):
    label = window.title_bar.findChild(QLabel, "titlebar-title")
    assert label is not None
    assert label.text() == window.windowTitle()


def test_title_bar_close_button_hides_window_to_tray(window, monkeypatch, qtbot):
    monkeypatch.setattr("mktsk.gui.tray.tray_available", lambda: True)
    tray = TrayController(window)
    window.tray_controller = tray
    qtbot.mouseClick(window.title_bar.close_button, Qt.MouseButton.LeftButton)
    assert window.isHidden()


def test_window_is_frameless(window):
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint


def test_resize_grips_are_children_of_the_central_widget(window):
    grips = window.resize_grips.grips
    assert len(grips) == 8
    central = window.centralWidget()
    assert central is not None
    for grip in grips:
        assert grip.parent() is central


def test_corner_grips_sit_at_the_corners_of_the_central_widget(window):
    central = window.centralWidget()
    assert central is not None
    size = central.size()
    grips = window.resize_grips.grips
    top_left = next(
        grip for grip in grips if grip.edges == Qt.Edge.TopEdge | Qt.Edge.LeftEdge
    )
    bottom_right = next(
        grip for grip in grips if grip.edges == Qt.Edge.BottomEdge | Qt.Edge.RightEdge
    )
    assert top_left.geometry().topLeft() == QPoint(0, 0)
    assert bottom_right.geometry().bottomRight() == QPoint(
        size.width() - 1, size.height() - 1
    )


def test_grips_are_hidden_when_maximized(window, monkeypatch):
    grips = window.resize_grips.grips
    assert all(not grip.isHidden() for grip in grips)

    window.showMaximized()
    if window.isMaximized():
        assert all(grip.isHidden() for grip in grips)
        window.showNormal()
        assert all(not grip.isHidden() for grip in grips)
        return

    # offscreen platforms do not always deliver the state change, so drive the
    # event filter the same way a real maximise or restore would
    monkeypatch.setattr(window, "isMaximized", lambda: True)
    QApplication.sendEvent(window, QEvent(QEvent.Type.WindowStateChange))
    assert all(grip.isHidden() for grip in grips)

    monkeypatch.setattr(window, "isMaximized", lambda: False)
    QApplication.sendEvent(window, QEvent(QEvent.Type.WindowStateChange))
    assert all(not grip.isHidden() for grip in grips)


def test_left_edge_press_asks_the_system_to_resize(window, monkeypatch):
    grips = window.resize_grips.grips
    left = next(grip for grip in grips if grip.edges == Qt.Edge.LeftEdge)
    handle = Mock()
    monkeypatch.setattr(window, "windowHandle", lambda: handle)
    QApplication.sendEvent(
        left,
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(),
            QPointF(),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )
    handle.startSystemResize.assert_called_once_with(Qt.Edge.LeftEdge)
