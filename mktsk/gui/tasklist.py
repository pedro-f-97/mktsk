"""The tasks of a category as a list, with the actions on the selected row."""

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
    Signal,
    SignalInstance,
)
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLayout,
    QListWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QWidget,
)

from mktsk import listing

from .icons import _draw_folder, _draw_pencil, _draw_plus, _icon_button

_ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1

_ACTION_BAR_PADDING = 4


class _ActionBar(QWidget):
    """The actions offered for the selected task, aligned to the left.

    The buttons carry an icon and a tooltip rather than a label, which keeps the
    bar narrow enough to sit on a row without hiding much of it.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        # the listing positions the bar, so the layout must not resize it
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_ACTION_BAR_PADDING)

        self.open_button = _icon_button(
            self, "Open the task folder", _draw_folder, "OpenTask"
        )
        self.resume_button = _icon_button(
            self, "Add a note for today", _draw_plus, "ResumeTask"
        )
        self.rename_button = _icon_button(
            self, "Rename this task", _draw_pencil, "RenameTask"
        )
        for button in self.buttons():
            layout.addWidget(button)

    def buttons(self) -> tuple[QToolButton, ...]:
        """Returns the three action buttons, in order."""
        return (self.open_button, self.resume_button, self.rename_button)


class _InsetDelegate(QStyledItemDelegate):
    """Keeps the text of the row carrying the action bar clear of it.

    Only the selected row is inset, so the space for the buttons appears when the
    row is clicked and is given back when the selection goes. Every row keeps the
    height the bar needs, which stops the list from shifting as the selection
    moves.

    Args:
        inset: width reserved on the left of the selected row.
        min_height: height a row needs to hold the action bar.
    """

    def __init__(self, inset: int, min_height: int) -> None:
        super().__init__()
        self.inset = inset
        self.min_height = min_height
        self.inset_row = -1

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        option.rect = QRect(option.rect)
        if index.row() == self.inset_row:
            option.rect.adjust(self.inset, 0, 0, 0)
        super().paint(painter, option, index)

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), self.min_height))
        if index.row() == self.inset_row:
            size.setWidth(size.width() + self.inset)
        return size


class TaskListing(QListWidget):
    """A list of tasks with an action bar over the selected row.

    The bar follows the selected row, and shows only when a task is selected.
    Headings are not selectable, so they never get one. The listing only reports
    which action was asked for, leaving the task logic to the window.
    """

    open_requested = Signal(object)
    resume_requested = Signal(object)
    rename_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action_bar = _ActionBar(self.viewport())
        self.inset = self.action_bar.minimumSizeHint().width() + 2 * _ACTION_BAR_PADDING
        self.delegate = _InsetDelegate(
            self.inset, self.action_bar.minimumSizeHint().height()
        )
        self.setItemDelegate(self.delegate)

        self.action_bar.open_button.clicked.connect(
            lambda: self._request(self.open_requested)
        )
        self.action_bar.resume_button.clicked.connect(
            lambda: self._request(self.resume_requested)
        )
        self.action_bar.rename_button.clicked.connect(
            lambda: self._request(self.rename_requested)
        )
        self.currentItemChanged.connect(lambda *_: self._sync_action_bar())
        self.action_bar.hide()

    def selected_entry(self) -> listing.TaskEntry | None:
        """Returns the task of the selected row, or None when none is."""
        item = self.currentItem()
        return item.data(_ENTRY_ROLE) if item else None

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self._place_action_bar()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_action_bar()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_action_bar()

    def _request(self, signal: SignalInstance) -> None:
        entry = self.selected_entry()
        if entry is not None:
            signal.emit(entry)

    def _sync_action_bar(self) -> None:
        self.delegate.inset_row = self.currentRow()
        self.viewport().update()

        if self.selected_entry() is None:
            self.action_bar.hide()
            return

        # showing first, then placing: showing a widget with a layout lets the
        # layout resize it to its own idea of a size
        self.action_bar.show()
        self._place_action_bar()

    def _place_action_bar(self) -> None:
        item = self.currentItem()
        if item is None or item.data(_ENTRY_ROLE) is None:
            return

        rect = self.visualItemRect(item)
        self.action_bar.setGeometry(rect.left(), rect.top(), self.inset, rect.height())
