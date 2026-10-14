"""The icons the interface draws, and the button that carries one.

Drawing them in code keeps the package free of image files, so nothing has to be
collected for a frozen build.
"""

import math
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QApplication, QToolButton, QWidget

_ICON_SIZE = 18
_ICON_STROKE = 2.0


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
        QPolygonF(
            [
                QPointF(2, 5),
                QPointF(7, 5),
                QPointF(8.5, 7),
                QPointF(16, 7),
                QPointF(16, 15),
                QPointF(2, 15),
            ]
        )
    )


def _draw_plus(painter: QPainter, box: QRectF) -> None:
    """Draws a plus, for adding an intervention to a task."""
    painter.drawLine(QPointF(9, 4), QPointF(9, 14))
    painter.drawLine(QPointF(4, 9), QPointF(14, 9))


def _draw_pencil(painter: QPainter, box: QRectF) -> None:
    """Draws a pencil, for changing the title of a task."""
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(3.5, 14.5),
                QPointF(6.1, 14.1),
                QPointF(14.1, 6.1),
                QPointF(11.9, 3.9),
                QPointF(3.9, 11.9),
            ]
        )
    )
    painter.drawLine(QPointF(10.4, 5.5), QPointF(12.5, 7.6))


def _draw_state(painter: QPainter, box: QRectF) -> None:
    """Draws a ring with a dot, for the state a task is in."""
    painter.drawEllipse(QPointF(9, 9), 6, 6)
    painter.drawEllipse(QPointF(9, 9), 1.5, 1.5)


def _draw_close(painter: QPainter, box: QRectF) -> None:
    """Draws an archive box with a lid, for closing a task into one."""
    painter.drawRect(QRectF(2, 3, 14, 5))
    painter.drawRect(QRectF(4, 8, 10, 7))
    painter.drawLine(QPointF(7.5, 5.5), QPointF(10.5, 5.5))


def _draw_reopen(painter: QPainter, box: QRectF) -> None:
    """Draws a circular arrow turning counter-clockwise, for restoring."""
    painter.drawArc(QRectF(4, 4, 10, 10), 1440, 4320)
    painter.drawLine(QPointF(14, 9), QPointF(11.9, 11.1))
    painter.drawLine(QPointF(14, 9), QPointF(16.1, 11.1))


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


def _icon_button(
    parent: QWidget,
    tooltip: str,
    draw: Callable[[QPainter, QRectF], None],
    name: str,
) -> QToolButton:
    """Builds a button that carries an icon and a tooltip rather than a label.

    The icon is drawn twice, once from the enabled palette and once from the
    disabled group, so a disabled button fades with the rest of the interface
    rather than keeping its full colour. The tooltip is also the accessible
    name, so the button is found by what it does.

    Args:
        parent: the widget the button belongs to.
        tooltip: text shown on hover, and the accessible name.
        draw: painting function of the icon.
        name: role of the button, for the object name.

    Returns:
        The button.
    """
    button = QToolButton(parent)
    button.setObjectName(f"{name}Button")
    palette = button.palette()
    icon = _stroked_icon(palette.color(QPalette.ColorRole.ButtonText), draw)
    faded = _stroked_icon(
        palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText),
        draw,
    )
    icon.addPixmap(faded.pixmap(QSize(_ICON_SIZE, _ICON_SIZE)), QIcon.Mode.Disabled)
    button.setIcon(icon)
    button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setAutoRaise(True)
    return button
