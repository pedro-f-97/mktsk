"""The reminders UI: icons, row buttons, the add dialog, the list and the popup."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor

from mktsk.gui.icons import _draw_bell, _draw_bell_plus, _stroked_icon


def test_both_bell_icons_draw_at_several_sizes(qapp):
    for draw in (_draw_bell, _draw_bell_plus):
        icon = _stroked_icon(QColor("#000000"), draw)
        assert icon.isNull() is False
        for size in (12, 16, 18, 24):
            assert icon.pixmap(QSize(size, size)).isNull() is False
