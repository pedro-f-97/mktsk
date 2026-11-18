"""The drawn icons and the hint must follow the application palette.

When the system theme switches from light to dark without closing the program,
every component that draws its own colour has to re-derive it from the current
palette. The rest of the interface already does this: it reads palette roles at
paint time, so a re-polish of the window is enough. The drawn icons and the
``New tasks in ...`` hint froze their colour at build time, so they stay in the
light colour and become almost imperceptible in dark mode.
"""

from collections import Counter

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from mktsk.gui import MainWindow

_ICON_SIZE = 18


def _theme(text: str, button_text: str) -> QPalette:
    """Builds a palette; light when the text is dark, dark when it is white."""
    dark = text == "#ffffff"
    palette = QPalette()
    palette.setColor(
        QPalette.ColorRole.Window, QColor("#2b2b2b" if dark else QColor("#ffffff"))
    )
    palette.setColor(QPalette.ColorRole.Text, QColor(text))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(button_text))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
    palette.setColor(
        QPalette.ColorRole.Base, QColor("#3b3b3b" if dark else QColor("#ffffff"))
    )
    return palette


def _ink(icon) -> QColor:
    """The dominant colour of an icon's essentially opaque painted pixels.

    Antialiased edge pixels carry partial alpha and are ignored, so the result
    is the solid stroke colour the icon is drawn with.
    """
    image = icon.pixmap(QSize(_ICON_SIZE, _ICON_SIZE)).toImage()
    counts = Counter()
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() > 200:
                counts[color.rgb()] += 1
    return QColor.fromRgb(counts.most_common(1)[0][0])


def _switch_theme(window: MainWindow, palette: QPalette) -> None:
    """Simulates the system theme changing while the window stays open.

    This is what makes widgets re-resolve their colours from the new
    application palette, the same way a real theme change re-polishes the
    window. Widgets that kept an explicit colour keep it; the rest follow.
    """
    app = QApplication.instance()
    app.setPalette(palette)
    style = window.style()
    style.unpolish(window)
    style.polish(window)
    app.processEvents()


def test_the_hint_follows_the_palette(window, qapp):
    _switch_theme(window, _theme("#000000", "#000000"))
    before = window.target_label.palette().color(QPalette.ColorRole.WindowText)
    assert before == QColor("#000000")

    _switch_theme(window, _theme("#ffffff", "#ffffff"))

    after = window.target_label.palette().color(QPalette.ColorRole.WindowText)
    assert after == QColor("#ffffff")


def test_the_drawn_icon_follows_the_palette(window, qapp):
    _switch_theme(window, _theme("#000000", "#000000"))
    before = _ink(window.refresh_button.icon())
    assert before == QColor("#000000")

    _switch_theme(window, _theme("#ffffff", "#ffffff"))

    after = _ink(window.refresh_button.icon())
    dark = QColor("#ffffff")
    assert after != before
    assert after == dark
