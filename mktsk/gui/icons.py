"""The icons the interface draws, and the button that carries one.

Drawing them in code keeps the package free of image files, so nothing has to be
collected for a frozen build.
"""

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
from PySide6.QtWidgets import QToolButton, QWidget

_ICON_SIZE = 18
_ICON_STROKE = 2.0
_ICON_SCALE = 2


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


def _stroked_icon(color: QColor, draw: Callable[[QPainter, QRectF], None]) -> QIcon:
    """Renders a stroked icon on a transparent image.

    Drawing them in code keeps the package free of image files, so nothing has to
    be collected for a frozen build. The image is drawn at twice the size and
    halved by the device pixel ratio, so the strokes stay sharp on a HiDPI screen.

    Args:
        color: colour of the strokes.
        draw: painting function, given a painter and the box to draw in.

    Returns:
        The rendered icon.
    """
    image = QImage(
        _ICON_SIZE * _ICON_SCALE,
        _ICON_SIZE * _ICON_SCALE,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.setDevicePixelRatio(_ICON_SCALE)
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
    button.setIcon(
        _stroked_icon(
            button.palette().color(QPalette.ColorRole.ButtonText), draw
        )
    )
    button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
    button.setToolTip(tooltip)
    button.setAutoRaise(True)
    return button
