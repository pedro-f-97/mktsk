"""The application icon, drawn in code.

Keeping the drawing here means the window icon needs no image file at runtime,
and the generator script can build the committed assets from the same geometry.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

_BASE_SIZE = 100.0

# the drawing sits between x 15 and 75 and between y 20 and 95 of the base
# grid, so it is moved by these amounts to stand in the middle of it
_CENTER_OFFSET_X = 5.0
_CENTER_OFFSET_Y = -7.5


def _stroke_widths(size: int) -> tuple[float, float]:
    """Returns the outline and inner stroke widths for an icon size.

    Args:
        size: side of the icon in pixels.

    Returns:
        The outline and inner widths, in the 100-unit base grid. Small sizes
        carry thicker strokes so the icon stays legible.
    """
    if size <= 24:
        return (16.0, 9.0)
    if size <= 32:
        return (12.0, 6.5)
    if size <= 64:
        return (9.0, 5.0)
    return (7.0, 3.5)


def _draw_outlined_path(
    painter: QPainter,
    path: QPainterPath,
    outline_width: float,
    inner_width: float,
    cap_style: Qt.PenCapStyle = Qt.PenCapStyle.RoundCap,
    join_style: Qt.PenJoinStyle = Qt.PenJoinStyle.RoundJoin,
) -> None:
    """Strokes a path with a white outline and a black line over it."""
    pen = QPen(QColor("white"))
    pen.setWidthF(outline_width)
    pen.setCapStyle(cap_style)
    pen.setJoinStyle(join_style)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)

    pen = QPen(QColor("black"))
    pen.setWidthF(inner_width)
    pen.setCapStyle(cap_style)
    pen.setJoinStyle(join_style)
    painter.setPen(pen)
    painter.drawPath(path)


def _draw_app_icon(painter: QPainter, box: QRectF, size: int) -> None:
    """Draws the icon geometry inside a square box."""
    painter.save()
    try:
        scale = min(box.width(), box.height()) / _BASE_SIZE
        offset_x = box.left() + (box.width() - _BASE_SIZE * scale) / 2.0
        offset_y = box.top() + (box.height() - _BASE_SIZE * scale) / 2.0

        painter.translate(offset_x, offset_y)
        painter.scale(scale, scale)
        # the drawing is off-centre on the base grid, so it is moved to the
        # middle of it before anything is stroked
        painter.translate(_CENTER_OFFSET_X, _CENTER_OFFSET_Y)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outline_width, inner_width = _stroke_widths(size)

        silhouette = QPainterPath()
        silhouette.moveTo(15, 25)
        silhouette.lineTo(15, 23)
        silhouette.lineTo(18, 20)
        silhouette.lineTo(35, 20)
        silhouette.lineTo(45, 30)
        silhouette.lineTo(45, 35)
        silhouette.lineTo(60, 35)
        silhouette.lineTo(60, 50)
        silhouette.lineTo(75, 50)
        silhouette.lineTo(75, 85)
        silhouette.lineTo(65, 95)
        silhouette.lineTo(45, 95)
        silhouette.lineTo(35, 85)
        silhouette.lineTo(35, 80)
        silhouette.lineTo(25, 80)
        silhouette.lineTo(15, 70)
        silhouette.closeSubpath()

        diagonals = QPainterPath()
        diagonals.moveTo(25, 40)
        diagonals.lineTo(57, 64)
        diagonals.moveTo(25, 58)
        diagonals.lineTo(57, 82)

        _draw_outlined_path(
            painter,
            silhouette,
            outline_width=outline_width,
            inner_width=inner_width,
            cap_style=Qt.PenCapStyle.FlatCap,
            join_style=Qt.PenJoinStyle.MiterJoin,
        )
        _draw_outlined_path(
            painter,
            diagonals,
            outline_width=outline_width,
            inner_width=inner_width,
            cap_style=Qt.PenCapStyle.RoundCap,
            join_style=Qt.PenJoinStyle.RoundJoin,
        )
    finally:
        painter.restore()


def render_icon_image(size: int) -> QImage:
    """Renders the icon into a transparent square image.

    Args:
        size: side of the image in pixels.

    Returns:
        An ARGB image of the icon, without needing a QApplication.
    """
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _draw_app_icon(painter, QRectF(0, 0, size, size), size)
    finally:
        painter.end()
    return image


def app_icon() -> QIcon:
    """Builds the window icon with one pixmap per supported size."""
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(render_icon_image(size)))
    return icon
