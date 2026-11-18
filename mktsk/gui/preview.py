"""The preview of the selected task: its notes and its attachments."""

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeyEvent, QStandardItemModel
from PySide6.QtWidgets import (
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from mktsk import helpers, listing, standards

from .selection import _UnifiedSelectionDelegate


def _task_text(file: Path) -> str:
    """Reads the raw text of a task .md for the preview.

    A file that cannot be read previews as empty, and bytes that are not valid
    utf-8 are replaced, so one bad file never breaks the preview.

    Args:
        file: the .md of the task.

    Returns:
        The text of the file, or an empty string when it cannot be read.
    """
    try:
        return file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _panel_title(text: str) -> QHeaderView:
    """Builds a read-only panel title with the native header look.

    Args:
        text: the title of the panel.

    Returns:
        A one-section header showing the title.
    """
    model = QStandardItemModel()
    model.setColumnCount(1)
    model.setHorizontalHeaderLabels([text])
    header = QHeaderView(Qt.Orientation.Horizontal)
    header.setModel(model)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return header


def _set_panel_title(header: QHeaderView, text: str) -> None:
    """Replaces the title a header built by `_panel_title` carries.

    Args:
        header: the panel title.
        text: the title to show.
    """
    model = header.model()
    if model is not None:
        model.setHeaderData(0, Qt.Orientation.Horizontal, text)


def _titled(header: QHeaderView, content: QWidget) -> QWidget:
    """Stacks a panel title over its content."""
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(header)
    layout.addWidget(content, 1)
    return panel


class PreviewPanel(QSplitter):
    """The raw text of the selected task beside the files it carries.

    Both halves are read-only and stay out of the tab order, except the
    attachment list, where double-click or Enter opens an entry. A closed task
    is read from inside its archive, which is never extracted: its entries
    open the archive itself.

    Args:
        parent: the widget the panel belongs to.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._entry: listing.TaskEntry | None = None
        self._archived = False

        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.preview_list = QListWidget()
        self.preview_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.preview_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.preview_list.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.preview_list.setAlternatingRowColors(True)
        self.preview_list.setItemDelegate(_UnifiedSelectionDelegate(self.preview_list))
        self.preview_list.itemDoubleClicked.connect(self.open_attachment)
        self.preview_list.keyPressEvent = self._list_key_press

        self.preview_text_header = _panel_title("Details")
        self.preview_list_header = _panel_title("Attachments")
        self.preview_text_panel = _titled(self.preview_text_header, self.preview_text)
        self.preview_list_panel = _titled(self.preview_list_header, self.preview_list)
        self.addWidget(self.preview_text_panel)
        self.addWidget(self.preview_list_panel)
        self.setStretchFactor(0, 3)
        self.setStretchFactor(1, 1)
        # hidden until a task is selected, so the table keeps the full height
        self.hide()

    def show_entry(self, entry: listing.TaskEntry | None) -> None:
        """Shows a task, read again from disk, or hides the panel for None.

        Args:
            entry: the selected task, or None when no task is selected.
        """
        self._entry = entry
        if entry is None:
            self.hide()
            return

        archived = standards.is_task_archive(entry.file.name)
        if archived:
            text, attachments = listing.read_archived_task(entry.file)
            folder = entry.file
        else:
            text = _task_text(entry.file)
            attachments = listing.list_attachments(entry.file.parent)
            folder = entry.file.parent

        self.preview_text.setPlainText(text)
        _set_panel_title(
            self.preview_text_header, "Details (archived)" if archived else "Details"
        )
        self.preview_list.clear()
        for name in attachments:
            item = QListWidgetItem(name)
            # subfolders carry a trailing '/', and an archived entry opens the archive
            path = folder if archived else folder / name.rstrip("/")
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.preview_list.addItem(item)
        self._archived = archived
        self.preview_list.setToolTip(
            "Double-click opens the archive (.zip)" if archived else ""
        )
        # without attachments the text takes the full width
        self.preview_list.setVisible(bool(attachments))
        self.preview_list_panel.setVisible(bool(attachments))
        self.show()

    def open_attachment(self, item: QListWidgetItem) -> None:
        """Opens an attachment with the default application.

        A missing file is reported and the task read again; an archived entry
        opens the archive itself.

        Args:
            item: the attachment row.
        """
        path = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path, Path):
            return
        if not path.exists():
            QMessageBox.warning(self, "mktsk", f"Attachment no longer exists: {path}")
            self.show_entry(self._entry)
            return
        if self._archived:
            try:
                helpers.open_file(path)
            except OSError as error:
                QMessageBox.warning(self, "mktsk", str(error))
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, "mktsk", f"Could not open: {path}")

    def _list_key_press(self, event: QKeyEvent) -> None:
        """Opens the current attachment on Enter; other keys navigate."""
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            item = self.preview_list.currentItem()
            if item is not None:
                self.open_attachment(item)
                return
        QListWidget.keyPressEvent(self.preview_list, event)
