"""The bar that hides and shows the left pane."""

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QToolButton, QWidget

from .icons import _CHEVRON_HALF_HEIGHT, _draw_chevron

# the separator line of the toggle bar: how far it stops short of the ends of
# the bar, and of the chevron it is interrupted by, in logical pixels
_TOGGLE_LINE_MARGIN = 6.0
_TOGGLE_LINE_GAP = 4.0


class PaneToggle(QToolButton):
    """The pane toggle, drawn as a line down its centre broken by a chevron.

    The direction of the chevron is handed in by the window, from the same
    state that words the tooltip, so the bar paints what it is told.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._points_right = False

    def set_points_right(self, points_right: bool) -> None:
        """Turns the chevron to the side the next click opens, and repaints.

        Args:
            points_right: True for a chevron pointing right.
        """
        self._points_right = points_right
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        chevron_colour = palette.color(QPalette.ColorRole.ButtonText)
        idle = palette.color(QPalette.ColorRole.Mid)
        line_colour = chevron_colour if self.underMouse() else idle
        centre = self.rect().center()
        x = centre.x()
        painter.setPen(QPen(line_colour, 1))
        painter.drawLine(
            QPointF(x, _TOGGLE_LINE_MARGIN),
            QPointF(x, centre.y() - _CHEVRON_HALF_HEIGHT - _TOGGLE_LINE_GAP),
        )
        painter.drawLine(
            QPointF(x, centre.y() + _CHEVRON_HALF_HEIGHT + _TOGGLE_LINE_GAP),
            QPointF(x, self.height() - _TOGGLE_LINE_MARGIN),
        )
        _draw_chevron(painter, QRectF(self.rect()), self._points_right, chevron_colour)
        painter.end()
