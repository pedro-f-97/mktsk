"""Tests for the TitleBar widget skeleton."""

from PySide6.QtCore import QMargins
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QLabel, QToolButton, QWidget

from mktsk.gui.titlebar import TITLEBAR_HEIGHT, TitleBar


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
