"""Generates the committed icon assets from the drawing of the application.

The window icon is drawn in code by `mktsk/gui/app_icon.py`, and this script
renders that same drawing into `assets/app.ico` and `assets/app.png`, the files
the executable takes as its icon. Run it only when the drawing changes:

    python tools/make_icon.py
"""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

# the script runs from the repository, where the package sits one folder up
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mktsk.gui.app_icon import ICON_SIZES, render_icon_image

# the header of an icon file: the reserved field, the type and the number of
# images that follow
_ICO_HEADER = struct.Struct("<HHH")

# one entry per image: the width and the height as bytes, the colour count,
# the reserved byte, the colour planes, the bits per pixel, the size of the
# image data and where that data starts
_ICO_ENTRY = struct.Struct("<BBBBHHII")

_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


def _png_bytes(image: QImage) -> bytes:
    """Encodes an image as PNG.

    Args:
        image: the image to encode.

    Returns:
        The bytes of the PNG file.
    """
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, b"PNG"):
        raise RuntimeError("Failed to encode image as PNG")
    return bytes(buffer.data().data())


def build_ico(images: list[QImage]) -> bytes:
    """Builds an icon file holding the given images.

    Every image is stored as a PNG, which the icon file points at with the
    size and the offset of each payload.

    Args:
        images: the images of the icon, one per size.

    Returns:
        The bytes of the icon file.
    """
    payloads = [_png_bytes(image) for image in images]
    count = len(payloads)
    offset = _ICO_HEADER.size + _ICO_ENTRY.size * count

    entries = []
    for image, payload in zip(images, payloads):
        size = image.width()
        entries.append(
            _ICO_ENTRY.pack(
                size % 256,  # a size of 256 is stored as zero
                size % 256,
                0,  # no colour table
                0,  # reserved
                1,  # colour planes
                32,  # bits per pixel
                len(payload),
                offset,
            )
        )
        offset += len(payload)

    return _ICO_HEADER.pack(0, 1, count) + b"".join(entries) + b"".join(payloads)


def main(out_dir: Path | None = None) -> None:
    """Writes the icon assets.

    Args:
        out_dir: where the files are written; the `assets` folder of the
            repository by default.
    """
    folder = out_dir or _ASSETS_DIR
    folder.mkdir(parents=True, exist_ok=True)

    images = [render_icon_image(size) for size in ICON_SIZES]
    icon = folder / "app.ico"
    icon.write_bytes(build_ico(images))
    picture = folder / "app.png"
    picture.write_bytes(_png_bytes(render_icon_image(256)))

    print(f"Wrote {icon}")
    print(f"Wrote {picture}")


if __name__ == "__main__":
    main()
