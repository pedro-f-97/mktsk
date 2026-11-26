"""Tests for the TitleBar widget skeleton."""

from unittest.mock import Mock

from PySide6.QtCore import QEvent, QMargins, QPointF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QMouseEvent,
    QPalette,
    QPixmap,
    QWindowStateChangeEvent,
)
from PySide6.QtWidgets import QApplication, QLabel, QToolButton, QWidget

from mktsk.gui.icons import (
    _ICON_SIZE,
    _draw_maximize,
    _draw_restore,
    _stroked_icon,
)
from mktsk.gui.titlebar import TITLEBAR_HEIGHT, TitleBar


def _mouse_event(event_type, button, buttons):
    """Builds a mouse event with an explicit pressed-button state."""
    return QMouseEvent(
        event_type,
        QPointF(),
        QPointF(),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def _send(bar, event_type, button, buttons):
    """Builds a mouse event and sends it straight to the bar."""
    QApplication.sendEvent(bar, _mouse_event(event_type, button, buttons))


def _patch_window_handle(window, monkeypatch):
    """Patches windowHandle to return a mock handle and returns it."""
    handle = Mock()
    monkeypatch.setattr(window, "windowHandle", lambda: handle)
    return handle


def _render(draw, color=None):
    """Renders an icon drawer to an image, like the icon tests do."""
    if color is None:
        color = QColor("#000000")
    icon = _stroked_icon(color, draw)
    return icon.pixmap(QSize(_ICON_SIZE, _ICON_SIZE)).toImage()


def _icon_image(button):
    """The image currently shown by an icon button."""
    return button.icon().pixmap(QSize(_ICON_SIZE, _ICON_SIZE)).toImage()


def _text_color(button):
    """The colour an icon button draws its icon in."""
    return button.palette().color(QPalette.ColorRole.ButtonText)


def test_titlebar_icon_label_exists(qapp, qtbot):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    icon_label = bar.findChild(QLabel, "titlebar-icon")
    assert icon_label is not None
    assert icon_label.pixmap() is not None
    assert not icon_label.pixmap().isNull()


def test_titlebar_title_label_matches_window(qapp, qtbot):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    title_label = bar.findChild(QLabel, "titlebar-title")
    assert title_label is not None
    assert title_label.text() == "Example task"


def test_titlebar_three_buttons(qapp, qtbot):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    layout = bar.layout()
    assert layout is not None
    assert layout.spacing() == 0
    assert layout.contentsMargins() == QMargins(4, 0, 0, 0)

    expected = (
        ("titlebar-minimize", "Minimize"),
        ("titlebar-maximize", "Maximize"),
        ("titlebar-close", "Close"),
    )
    for name, tooltip in expected:
        button = bar.findChild(QToolButton, name)
        assert button is not None
        assert button.toolTip() == tooltip


def test_titlebar_fixed_height(qapp, qtbot):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    assert bar.height() == TITLEBAR_HEIGHT


def test_minimize_button_calls_show_minimized(qapp, qtbot, monkeypatch):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    show_minimized = Mock()
    monkeypatch.setattr(window, "showMinimized", show_minimized)

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    qtbot.mouseClick(bar.minimize_button, Qt.MouseButton.LeftButton)
    show_minimized.assert_called_once()


def test_maximize_button_calls_show_maximized_when_normal(qapp, qtbot, monkeypatch):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    show_maximized = Mock()
    monkeypatch.setattr(window, "showMaximized", show_maximized)

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    qtbot.mouseClick(bar.maximize_button, Qt.MouseButton.LeftButton)
    show_maximized.assert_called_once()


def test_maximize_button_calls_show_normal_when_maximized(qapp, qtbot, monkeypatch):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))
    window.setWindowState(Qt.WindowState.WindowMaximized)

    show_normal = Mock()
    monkeypatch.setattr(window, "showNormal", show_normal)

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    qtbot.mouseClick(bar.maximize_button, Qt.MouseButton.LeftButton)
    show_normal.assert_called_once()


def test_close_button_calls_close(qapp, qtbot, monkeypatch):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    close = Mock()
    monkeypatch.setattr(window, "close", close)

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    qtbot.mouseClick(bar.close_button, Qt.MouseButton.LeftButton)
    close.assert_called_once()


def test_maximize_button_matches_window_state(qapp, qtbot):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    # normal: maximize icon and tooltip
    assert bar.maximize_button.toolTip() == "Maximize"
    normal_image = _icon_image(bar.maximize_button)
    assert normal_image == _render(_draw_maximize, _text_color(bar.maximize_button))

    # maximized: restore icon and tooltip, a different icon
    window.setWindowState(Qt.WindowState.WindowMaximized)
    qapp.sendEvent(window, QWindowStateChangeEvent(Qt.WindowState.WindowNoState))

    assert bar.maximize_button.toolTip() == "Restore"
    maximized_image = _icon_image(bar.maximize_button)
    assert maximized_image == _render(_draw_restore, _text_color(bar.maximize_button))
    assert maximized_image != normal_image


def test_maximize_button_follows_outside_state_change(qapp, qtbot):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    assert bar.maximize_button.toolTip() == "Maximize"
    normal_image = _icon_image(bar.maximize_button)

    # maximized from outside: switches to restore without a click
    window.setWindowState(Qt.WindowState.WindowMaximized)
    qapp.sendEvent(window, QWindowStateChangeEvent(Qt.WindowState.WindowNoState))
    assert bar.maximize_button.toolTip() == "Restore"
    assert _icon_image(bar.maximize_button) == _render(
        _draw_restore, _text_color(bar.maximize_button)
    )
    assert _icon_image(bar.maximize_button) != normal_image

    # back to normal: switches back to maximize
    window.setWindowState(Qt.WindowState.WindowNoState)
    qapp.sendEvent(window, QWindowStateChangeEvent(Qt.WindowState.WindowMaximized))
    assert bar.maximize_button.toolTip() == "Maximize"
    assert _icon_image(bar.maximize_button) == normal_image


def test_titlebar_title_follows_window_title(qapp, qtbot):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    title_label = bar.findChild(QLabel, "titlebar-title")
    assert title_label is not None
    assert title_label.text() == "Example task"

    window.setWindowTitle("Another task")
    assert title_label.text() == "Another task"


def test_titlebar_title_keeps_last_of_two_changes(qapp, qtbot):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    title_label = bar.findChild(QLabel, "titlebar-title")
    assert title_label is not None

    window.setWindowTitle("First title")
    assert title_label.text() == "First title"
    window.setWindowTitle("Second title")
    assert title_label.text() == "Second title"


def test_titlebar_title_can_be_empty(qapp, qtbot):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    title_label = bar.findChild(QLabel, "titlebar-title")
    assert title_label is not None

    window.setWindowTitle("")
    assert title_label.text() == ""


def test_drag_press_then_move_calls_start_system_move_once(qapp, qtbot, monkeypatch):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    handle = _patch_window_handle(window, monkeypatch)
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    _send(
        bar,
        QEvent.Type.MouseButtonPress,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    assert bar._drag_pending is True

    _send(
        bar, QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton
    )
    assert bar._drag_pending is False
    handle.startSystemMove.assert_called_once()


def test_move_without_press_does_not_call_start_system_move(qapp, qtbot, monkeypatch):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    handle = _patch_window_handle(window, monkeypatch)
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    _send(
        bar, QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton
    )
    handle.startSystemMove.assert_not_called()


def test_two_moves_after_one_press_call_start_system_move_once(
    qapp, qtbot, monkeypatch
):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    handle = _patch_window_handle(window, monkeypatch)
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    _send(
        bar,
        QEvent.Type.MouseButtonPress,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    _send(
        bar, QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton
    )
    _send(
        bar, QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton
    )
    handle.startSystemMove.assert_called_once()


def test_press_release_then_move_does_not_call_start_system_move(
    qapp, qtbot, monkeypatch
):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    handle = _patch_window_handle(window, monkeypatch)
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    _send(
        bar,
        QEvent.Type.MouseButtonPress,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    _send(
        bar,
        QEvent.Type.MouseButtonRelease,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
    )
    _send(
        bar, QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton
    )
    assert bar._drag_pending is False
    handle.startSystemMove.assert_not_called()


def test_right_button_press_then_move_does_not_call_start_system_move(
    qapp, qtbot, monkeypatch
):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    handle = _patch_window_handle(window, monkeypatch)
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    _send(
        bar,
        QEvent.Type.MouseButtonPress,
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
    )
    _send(
        bar, QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton
    )
    handle.startSystemMove.assert_not_called()


def test_drag_with_no_window_handle_does_not_raise(qapp, qtbot, monkeypatch):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    monkeypatch.setattr(window, "windowHandle", lambda: None)
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    _send(
        bar,
        QEvent.Type.MouseButtonPress,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    _send(
        bar, QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton
    )
    assert bar._drag_pending is False


def test_double_click_toggles_maximized_and_normal(qapp, qtbot, monkeypatch):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    show_maximized = Mock()
    show_normal = Mock()
    monkeypatch.setattr(window, "showMaximized", show_maximized)
    monkeypatch.setattr(window, "showNormal", show_normal)
    monkeypatch.setattr(window, "isMaximized", Mock(return_value=False))

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    _send(
        bar,
        QEvent.Type.MouseButtonDblClick,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    show_maximized.assert_called_once()
    show_normal.assert_not_called()

    monkeypatch.setattr(window, "isMaximized", Mock(return_value=True))
    _send(
        bar,
        QEvent.Type.MouseButtonDblClick,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    show_normal.assert_called_once()


def test_double_click_right_button_does_nothing(qapp, qtbot, monkeypatch):
    window = QWidget()
    window.setWindowTitle("Example task")
    window.setWindowIcon(QIcon(QPixmap(16, 16)))

    show_maximized = Mock()
    show_normal = Mock()
    monkeypatch.setattr(window, "showMaximized", show_maximized)
    monkeypatch.setattr(window, "showNormal", show_normal)

    bar = TitleBar(window)
    qtbot.addWidget(bar)

    _send(
        bar,
        QEvent.Type.MouseButtonDblClick,
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
    )
    show_maximized.assert_not_called()
    show_normal.assert_not_called()
