"""The tree of the current directory and the categories under it."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QToolButton, QTreeWidget, QWidget

from .icons import _draw_plus, _icon_button

_PATH_ROLE = Qt.ItemDataRole.UserRole

_HEADER_BUTTON_MARGIN = 4
_HEADER_ICON_SIZE = 12
_HEADER_BUTTONS = 3


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
        self._navigation: tuple[QToolButton, ...] = ()
        self.header_button = _icon_button(
            self.header(), "New category", _draw_plus, "NewCategory"
        )
        self.header_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.header_button.setIconSize(QSize(_HEADER_ICON_SIZE, _HEADER_ICON_SIZE))
        self.header_button.clicked.connect(self.category_requested.emit)
        self.header().geometriesChanged.connect(self._place_header_buttons)
        self.header_button.show()
        self._place_header_buttons()

    def set_header_label(self, text: str) -> None:
        """Sets the header label and widens the tree to keep it clear of the buttons.

        Three buttons share the header, so the narrowest the tree may be is the
        label plus the room those buttons need; without it the label runs under
        them when the tree is squeezed.

        Args:
            text: the header label.
        """
        self.setHeaderLabel(text)
        side = self.header_button.sizeHint().height()
        reserved = _HEADER_BUTTONS * side + (_HEADER_BUTTONS + 1) * _HEADER_BUTTON_MARGIN
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance(text) + reserved)

    def set_navigation_buttons(self, choose: QToolButton, up: QToolButton) -> None:
        """Takes the two navigation buttons to sit beside the category one.

        The tree only places them: creating and wiring them belongs to the
        window. They are given the size of the category button so the three read
        as one set.

        Args:
            choose: the button that opens the directory dialog.
            up: the button that walks to the parent directory.
        """
        self._navigation = (choose, up)
        for button in self._navigation:
            button.setParent(self.header())
            button.setIconSize(self.header_button.iconSize())
            button.show()
        self._place_header_buttons()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_header_buttons()

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

    def _place_header_buttons(self) -> None:
        """Places the header buttons at the right end, centred and apart.

        The category button stays at the right end where it was, and the
        navigation buttons follow it to the left, each as wide as the category
        button and squared off to the height of the header, so none of them
        overflows the row and the gaps between them are all the same.
        """
        header = self.header()
        side = min(self.header_button.sizeHint().height(), header.height())
        x = header.width() - _HEADER_BUTTON_MARGIN
        for button in reversed(self._header_buttons()):
            button.resize(side, side)
            x -= side
            button.move(x, (header.height() - side) // 2)
            x -= _HEADER_BUTTON_MARGIN

    def _header_buttons(self) -> list[QToolButton]:
        """Returns the header buttons, from the left, ending with the category one."""
        return [*self._navigation, self.header_button]
