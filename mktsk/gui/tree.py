"""The tree of the current directory and the categories under it."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QStyle,
    QStyleOptionHeader,
    QToolButton,
    QTreeWidget,
    QWidget,
)

from .icons import _draw_bell, _draw_plus, _icon_button

_PATH_ROLE = Qt.ItemDataRole.UserRole

_HEADER_BUTTON_MARGIN = 4
_HEADER_ICON_SIZE = 12


class _CategoryTree(QTreeWidget):
    """The directory tree, with a button on its header for a new category.

    The header is a QHeaderView of its own, held beside the tree in the left
    pane so the path can sit under it, and the tree's own header is hidden. It
    shares the tree's single section, so it carries the same `Directory` title.
    The button lives inside that header, at its right end, so it rides along
    with the header row instead of taking a row of its own. The tree only
    reports that the button was pressed, leaving the category logic to the
    window.
    """

    category_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._navigation: tuple[QToolButton, ...] = ()
        self._header_text = ""
        self.setHeaderHidden(True)
        self.header_view = QHeaderView(Qt.Orientation.Horizontal)
        self.header_view.setModel(self.model())
        self.header_view.setStretchLastSection(True)
        # the title starts where the path label is indented, so the two read as
        # one column; the default centres it over the section and would drift it
        # under the buttons
        self.header_view.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.header_button = _icon_button(
            self.header_view, "New category", _draw_plus, "NewCategory"
        )
        self.header_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.header_button.setIconSize(QSize(_HEADER_ICON_SIZE, _HEADER_ICON_SIZE))
        self.header_button.clicked.connect(self.category_requested.emit)
        # the bell shares the header but is hidden until a reminder scheduler
        # is attached, so a run without a tray offers no reminders to see
        self.bell_button = _icon_button(
            self.header_view, "Reminders", _draw_bell, "Reminders"
        )
        self.bell_button.setCheckable(True)
        self.bell_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bell_button.setIconSize(QSize(_HEADER_ICON_SIZE, _HEADER_ICON_SIZE))
        self.bell_button.hide()
        self.header_view.geometriesChanged.connect(self._place_header_buttons)
        self.header_view.geometriesChanged.connect(self._update_directory_header_label)
        self.header_button.show()
        self._place_header_buttons()

    def set_header_label(self, text: str) -> None:
        """Sets the header label and widens the tree to keep it clear of the buttons.

        The buttons share the header, so the narrowest the tree may be is the
        label plus the room those buttons need; without it the label runs under
        them when the tree is squeezed.

        Args:
            text: the header label.
        """
        self._header_text = text
        self.setHeaderLabel(text)
        side = self.header_button.sizeHint().height()
        shown = self._shown_header_buttons()
        reserved = len(shown) * side + (len(shown) + 1) * _HEADER_BUTTON_MARGIN
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance(text) + reserved)
        # a button that appeared or went changes where the others stand, so the
        # row is laid out again before the title is judged against it
        self._place_header_buttons()
        self._update_directory_header_label()

    def _update_directory_header_label(self) -> None:
        """Shows the header title only while it fits before the buttons.

        The buttons take the right end of the header, so the title has the room
        up to the leftmost one. When the header is narrower than the title and
        that room together, the title is dropped so the two never cross, and it
        comes back as soon as the header grows again.
        """
        room = self._shown_header_buttons()[0].x() - self.header_text_indent()
        text = self._header_text
        if self.header_view.fontMetrics().horizontalAdvance(text) > room:
            text = ""
        self.setHeaderLabel(text)

    def header_text_indent(self) -> int:
        """Returns the left padding the header gives its title.

        The window lines the path up with it, so the header and the path read as
        one column.

        Returns:
            The padding, in pixels.
        """
        option = QStyleOptionHeader()
        option.rect = self.header_view.rect()
        option.section = 0
        option.state = QStyle.StateFlag.State_Enabled
        return self.header_view.style().subElementRect(
            QStyle.SubElement.SE_HeaderLabel, option, self.header_view
        ).left()

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
            button.setParent(self.header_view)
            button.setIconSize(self.header_button.iconSize())
            button.show()
        self.set_header_label(self._header_text)

    def show_bell(self) -> None:
        """Shows the reminders button and makes room for it in the header.

        The bell stays hidden until a reminder scheduler is attached, so a run
        without a tray offers no reminders panel to reach.
        """
        self.bell_button.show()
        self.set_header_label(self._header_text)

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

    def clear_subdirectory(self) -> None:
        """Drops the selection, so no subdirectory is the target any more.

        The current item carries the selection, so an invalid index is what
        takes it away; that is also the one way to a current item of None,
        which the selection-change signal reports like any other.
        """
        self.setCurrentIndex(self.model().index(-1, -1))

    def _place_header_buttons(self) -> None:
        """Places the header buttons at the right end, centred and apart.

        The category button stays at the right end where it was, and the
        navigation buttons follow it to the left, each as wide as the category
        button and squared off to the height of the header, so none of them
        overflows the row and the gaps between them are all the same.
        """
        header = self.header_view
        side = min(self.header_button.sizeHint().height(), header.height())
        x = header.width() - _HEADER_BUTTON_MARGIN
        for button in reversed(self._shown_header_buttons()):
            button.resize(side, side)
            x -= side
            button.move(x, (header.height() - side) // 2)
            x -= _HEADER_BUTTON_MARGIN

    def _header_buttons(self) -> list[QToolButton]:
        """Returns the header buttons, from the left, ending with the bell."""
        return [*self._navigation, self.header_button, self.bell_button]

    def _shown_header_buttons(self) -> list[QToolButton]:
        """Returns the header buttons that are not hidden, from the left."""
        return [button for button in self._header_buttons() if not button.isHidden()]
