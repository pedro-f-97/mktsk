"""The icons the interface draws, and the button that carries one.

Drawing them in code keeps the package free of image files, so nothing has to be
collected for a frozen build.
"""

import math
from collections.abc import Callable

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QApplication, QToolButton, QWidget

_ICON_SIZE = 18
_ICON_STROKE = 2.0

# the size of an icon that sits beside a line of text rather than alone in a
# header, so it reads as part of the line instead of as a button of its own
_SMALL_ICON_SIZE = 12

_CLIP_TOP = 3.5
_CLIP_BOTTOM = 14.5
_CLIP_WIDTH = 6.0
_CLIP_INNER_INSET = 3.0
_CLIP_TAIL = 4.5

# how far the chevron of the pane toggle reaches from its centre, small enough
# to sit inside the toggle bar with a margin on each side
_CHEVRON_HALF_WIDTH = 3.5
_CHEVRON_HALF_HEIGHT = 5.5


def _device_scale() -> int:
    """Returns the device pixel ratio the icons are rendered at.

    Drawing at the ratio of the screen keeps the strokes sharp on a HiDPI
    display without a second set of images.

    Returns:
        The scale factor, at least 1.
    """
    screen = QApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen is not None else 1.0
    return max(1, math.ceil(ratio))


def _icon_pen(color: QColor) -> QPen:
    """Builds the pen every icon is stroked with.

    Args:
        color: colour of the strokes.

    Returns:
        A round capped and joined pen, so the icons read as a set.
    """
    pen = QPen(color, _ICON_STROKE)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _draw_folder(painter: QPainter, box: QRectF) -> None:
    """Draws a closed folder with a tab, for showing where a task lives."""
    painter.drawPolygon(
        QPolygonF([
            QPointF(2, 5),
            QPointF(7, 5),
            QPointF(8.5, 7),
            QPointF(16, 7),
            QPointF(16, 15),
            QPointF(2, 15),
        ])
    )


def _draw_plus(painter: QPainter, box: QRectF) -> None:
    """Draws a plus, for adding an intervention to a task."""
    painter.drawLine(QPointF(9, 4), QPointF(9, 14))
    painter.drawLine(QPointF(4, 9), QPointF(14, 9))


def _draw_cross(painter: QPainter, box: QRectF) -> None:
    """Draws two crossing strokes, for clearing the destination."""
    painter.drawLine(QPointF(5, 5), QPointF(13, 13))
    painter.drawLine(QPointF(13, 5), QPointF(5, 13))


def _draw_pencil(painter: QPainter, box: QRectF) -> None:
    """Draws a pencil, for changing the title of a task."""
    painter.drawPolygon(
        QPolygonF([
            QPointF(3.5, 14.5),
            QPointF(6.1, 14.1),
            QPointF(14.1, 6.1),
            QPointF(11.9, 3.9),
            QPointF(3.9, 11.9),
        ])
    )
    painter.drawLine(QPointF(10.4, 5.5), QPointF(12.5, 7.6))


def _draw_state(painter: QPainter, box: QRectF) -> None:
    """Draws a ring with a dot, for the state a task is in."""
    painter.drawEllipse(QPointF(9, 9), 6, 6)
    painter.drawEllipse(QPointF(9, 9), 1.5, 1.5)


def _draw_clip(painter: QPainter, box: QRectF) -> None:
    """Draws a paperclip, for the attachments a task carries.

    A slim wire of two straight legs joined by a wide rounded turn at the
    bottom and a narrow one at the top, so the clip is tall and curved
    rather than angular.
    """
    centre = box.center().x()
    left = centre - _CLIP_WIDTH / 2
    right = centre + _CLIP_WIDTH / 2
    inner = left + _CLIP_INNER_INSET
    outer_radius = _CLIP_WIDTH / 2
    inner_radius = (right - inner) / 2

    path = QPainterPath()
    path.moveTo(left, _CLIP_TOP)
    path.lineTo(left, _CLIP_BOTTOM - outer_radius)
    path.arcTo(
        QRectF(left, _CLIP_BOTTOM - _CLIP_WIDTH, _CLIP_WIDTH, _CLIP_WIDTH),
        180,
        180,
    )
    path.lineTo(right, _CLIP_TOP + inner_radius)
    path.arcTo(
        QRectF(inner, _CLIP_TOP, right - inner, right - inner),
        0,
        180,
    )
    path.lineTo(inner, _CLIP_TOP + inner_radius + _CLIP_TAIL)
    painter.drawPath(path)


def _draw_close(painter: QPainter, box: QRectF) -> None:
    """Draws an archive box with a lid, for closing a task into one."""
    painter.drawRect(QRectF(2, 3, 14, 5))
    painter.drawRect(QRectF(4, 8, 10, 7))
    painter.drawLine(QPointF(7.5, 5.5), QPointF(10.5, 5.5))


def _draw_minimize(painter: QPainter, box: QRectF) -> None:
    """Draws a horizontal line, for minimizing the window."""
    painter.drawLine(QPointF(4, 9), QPointF(14, 9))


def _draw_maximize(painter: QPainter, box: QRectF) -> None:
    """Draws a square outline, for maximizing the window."""
    painter.drawRect(QRectF(4, 4, 10, 10))


def _draw_restore(painter: QPainter, box: QRectF) -> None:
    """Draws two overlapping squares, for restoring the window.

    The front square sits down-left and is drawn whole; the back square sits
    up-right and only its top and right edges show.
    """
    painter.drawRect(QRectF(2, 6, 10, 10))
    painter.drawLine(QPointF(6, 2), QPointF(16, 2))
    painter.drawLine(QPointF(16, 2), QPointF(16, 10))


def _draw_window_close(painter: QPainter, box: QRectF) -> None:
    """Draws two crossing diagonals, for closing the window."""
    painter.drawLine(QPointF(4, 4), QPointF(14, 14))
    painter.drawLine(QPointF(14, 4), QPointF(4, 14))


def _draw_reopen(painter: QPainter, box: QRectF) -> None:
    """Draws a circular arrow turning counter-clockwise, for restoring."""
    painter.drawArc(QRectF(4, 4, 10, 10), 1440, 4320)
    painter.drawLine(QPointF(14, 9), QPointF(11.9, 11.1))
    painter.drawLine(QPointF(14, 9), QPointF(16.1, 11.1))


def _draw_bell(painter: QPainter, box: QRectF) -> None:
    """Draws a bell with a clapper, for the reminders of a task.

    Args:
        painter: painter over the icon, given the pen the icons are drawn with.
        box: rectangle the icon is drawn in, unused because the strokes sit on
            the shared grid.
    """
    path = QPainterPath()
    path.moveTo(9, 3)
    path.cubicTo(6.4, 3, 4.8, 5.4, 4.8, 8.8)
    path.lineTo(4.8, 9.8)
    path.lineTo(2.8, 12)
    path.lineTo(15.2, 12)
    path.lineTo(13.2, 9.8)
    path.lineTo(13.2, 8.8)
    path.cubicTo(13.2, 5.4, 11.6, 3, 9, 3)
    painter.drawPath(path)
    painter.drawArc(QRectF(7.6, 12, 2.8, 2.8), 180 * 16, 180 * 16)


def _draw_choose(painter: QPainter, box: QRectF) -> None:
    """Draws a folder with an arrow, for choosing a directory with a dialog."""
    _draw_folder(painter, box)
    painter.drawLine(QPointF(7, 11), QPointF(12, 11))
    painter.drawLine(QPointF(12, 11), QPointF(10, 9))
    painter.drawLine(QPointF(12, 11), QPointF(10, 13))


def _draw_up(painter: QPainter, box: QRectF) -> None:
    """Draws an up arrow, for walking to the parent directory."""
    painter.drawLine(QPointF(9, 14), QPointF(9, 5))
    painter.drawLine(QPointF(9, 5), QPointF(5, 9))
    painter.drawLine(QPointF(9, 5), QPointF(13, 9))


def _draw_refresh(painter: QPainter, box: QRectF) -> None:
    """Draws a circular arrow turning clockwise, for reloading the listing."""
    painter.drawArc(QRectF(4, 4, 10, 10), 1440, -4320)
    painter.drawLine(QPointF(4, 9), QPointF(6.1, 11.1))
    painter.drawLine(QPointF(4, 9), QPointF(1.9, 11.1))


def _draw_content(painter: QPainter, box: QRectF) -> None:
    """Draws a document with two text lines, for searching inside tasks."""
    painter.drawLine(QPointF(2, 2), QPointF(14, 2))
    painter.drawLine(QPointF(14, 2), QPointF(14, 10))
    painter.drawLine(QPointF(2, 2), QPointF(2, 16))
    painter.drawLine(QPointF(2, 16), QPointF(16, 16))
    painter.drawLine(QPointF(14, 2), QPointF(16, 4))
    painter.drawLine(QPointF(16, 4), QPointF(16, 16))
    painter.drawLine(QPointF(4, 6), QPointF(13, 6))
    painter.drawLine(QPointF(4, 11), QPointF(12, 11))


def _draw_filter(painter: QPainter, box: QRectF) -> None:
    """Draws a funnel, for filtering the tasks by state."""
    painter.drawLine(QPointF(2, 3), QPointF(16, 3))
    painter.drawLine(QPointF(2, 3), QPointF(7.5, 9.5))
    painter.drawLine(QPointF(16, 3), QPointF(10.5, 9.5))
    painter.drawLine(QPointF(7.5, 9.5), QPointF(7.5, 15.5))
    painter.drawLine(QPointF(10.5, 9.5), QPointF(10.5, 13.5))
    painter.drawLine(QPointF(7.5, 15.5), QPointF(10.5, 13.5))


def _draw_chevron(
    painter: QPainter, box: QRectF, points_right: bool, color: QColor
) -> None:
    """Draws the two strokes of a chevron, for the pane toggle bar.

    Args:
        painter: painter over the bar, given the pen the icons are drawn with.
        box: rectangle to centre the chevron in.
        points_right: whether the tip points right rather than left.
        color: colour of the strokes.
    """
    painter.setPen(_icon_pen(color))
    centre = box.center()
    dx = _CHEVRON_HALF_WIDTH if points_right else -_CHEVRON_HALF_WIDTH
    back_x = centre.x() - dx
    painter.drawLine(
        QPointF(back_x, centre.y() - _CHEVRON_HALF_HEIGHT),
        QPointF(centre.x() + dx, centre.y()),
    )
    painter.drawLine(
        QPointF(centre.x() + dx, centre.y()),
        QPointF(back_x, centre.y() + _CHEVRON_HALF_HEIGHT),
    )


def _stroked_icon(color: QColor, draw: Callable[[QPainter, QRectF], None]) -> QIcon:
    """Renders a stroked icon on a transparent image.

    Drawing them in code keeps the package free of image files, so nothing has to
    be collected for a frozen build. The image is drawn at the device pixel ratio
    of the screen, so the strokes stay sharp on a HiDPI display.

    Args:
        color: colour of the strokes.
        draw: painting function, given a painter and the box to draw in.

    Returns:
        The rendered icon.
    """
    scale = _device_scale()
    image = QImage(
        _ICON_SIZE * scale,
        _ICON_SIZE * scale,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.setDevicePixelRatio(scale)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(_icon_pen(color))
    draw(painter, QRectF(0, 0, _ICON_SIZE, _ICON_SIZE))
    painter.end()

    return QIcon(QPixmap.fromImage(image))


class _IconButton(QToolButton):
    """A tool button whose icon is redrawn whenever the palette changes.

    The icon colour comes from the enabled `ButtonText` role, so a light or
    dark mode is followed without writing any colour down. The disabled copy is
    regenerated too, so a disabled button keeps fading with the interface.

    Args:
        parent: the widget the button belongs to.
        tooltip: text shown on hover, and the accessible name.
        draw: painting function of the icon.
        name: role of the button, for the object name.
    """

    def __init__(
        self,
        parent: QWidget,
        tooltip: str,
        draw: Callable[[QPainter, QRectF], None],
        name: str,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"{name}Button")
        self._draw = draw
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setAutoRaise(True)
        self._apply_icon()

    def _apply_icon(self) -> None:
        """Renders the icon from the current palette and installs it."""
        palette = self.palette()
        icon = _stroked_icon(palette.color(QPalette.ColorRole.ButtonText), self._draw)
        faded = _stroked_icon(
            palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText),
            self._draw,
        )
        icon.addPixmap(faded.pixmap(QSize(_ICON_SIZE, _ICON_SIZE)), QIcon.Mode.Disabled)
        self.setIcon(icon)
        self.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))

    def changeEvent(self, event: QEvent) -> None:
        """Redraws the icon when the palette changes (a theme switch)."""
        if event.type() == QEvent.Type.PaletteChange:
            self._apply_icon()
        super().changeEvent(event)


def _icon_button(
    parent: QWidget,
    tooltip: str,
    draw: Callable[[QPainter, QRectF], None],
    name: str,
) -> QToolButton:
    """Builds a button that carries an icon and a tooltip rather than a label.

    The icon is drawn from the enabled palette, so a disabled button fades with
    the rest of the interface, and the icon is redrawn when the palette changes
    so a light or dark mode is followed without writing any colour down. The
    tooltip is also the accessible name, so the button is found by what it does.

    Args:
        parent: the widget the button belongs to.
        tooltip: text shown on hover, and the accessible name.
        draw: painting function of the icon.
        name: role of the button, for the object name.

    Returns:
        The button.
    """
    return _IconButton(parent, tooltip, draw, name)
