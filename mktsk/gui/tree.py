"""The tree of the current directory and the categories under it."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QWidget

from .icons import _draw_plus, _icon_button

_PATH_ROLE = Qt.ItemDataRole.UserRole

_HEADER_BUTTON_MARGIN = 4
_HEADER_ICON_SIZE = 12


class _CategoryTree(QTreeWidget):
    """The directory tree, with a button on its header for a new category.

    The button lives inside the header widget, at its right end, so it rides
    along with the header row instead of taking a row of its own. The tree only
    reports that the button was pressed, leaving the category logic to the
    window.
    """

    category_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.header_button = _icon_button(
            self.header(), "New category", _draw_plus, "NewCategory"
        )
        self.header_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.header_button.setIconSize(QSize(_HEADER_ICON_SIZE, _HEADER_ICON_SIZE))
        self.header_button.clicked.connect(self.category_requested.emit)
        self.header().geometriesChanged.connect(self._place_header_button)
        self.header_button.show()
        self._place_header_button()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_header_button()

    def select_subdirectory(self, directory: Path) -> None:
        """Puts the selection on a subdirectory of the current directory.

        A directory that is not listed is left alone, so a selection that is no
        longer there simply falls away.

        Args:
            directory: the subdirectory to select.
        """
        # findItems only descends with MatchRecursive, and the stored path confirms
        # the text, so a name shared with another level is never picked
        flags = Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive
        for item in self.findItems(directory.name, flags, 0):
            if item.data(0, _PATH_ROLE) == str(directory):
                self.setCurrentItem(item)
                return

    def _place_header_button(self) -> None:
        """Puts the button at the right end of the header, centred in it.

        The button is squared off to the height of the header, so it never
        overflows the header row whatever the style asks of a tool button.
        """
        header = self.header()
        button = self.header_button
        side = min(button.sizeHint().height(), header.height())

        button.resize(side, side)
        button.move(
            header.width() - side - _HEADER_BUTTON_MARGIN,
            (header.height() - side) // 2,
        )
