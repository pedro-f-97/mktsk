"""The search panel: a live filter on task titles and an on-demand content search."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QPalette,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHeaderView,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mktsk import helpers, listing

from .icons import _draw_content, _icon_button
from .taskrow import _date_cell
from .tree import _HEADER_BUTTON_MARGIN, _HEADER_ICON_SIZE, _PATH_ROLE

_TITLE_PLACEHOLDER = "Search tasks"
_CONTENT_PLACEHOLDER = "Type and press Enter to search content"


class _SearchResults(QTreeWidget):
    """The results list, with a message painted when it is empty.

    The message is painted on the viewport rather than added as an item, so it
    is never selected or counted.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._empty_message = ""

    def set_empty_message(self, text: str) -> None:
        """Sets the message shown while the list is empty.

        Args:
            text: the message, or an empty string for none.
        """
        if self._empty_message == text:
            return
        self._empty_message = text
        self.viewport().update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self.topLevelItemCount() == 0 and self._empty_message:
            painter = QPainter(self.viewport())
            rect = self.viewport().rect()
            text = self.fontMetrics().elidedText(
                self._empty_message, Qt.TextElideMode.ElideRight, rect.width()
            )
            painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text
            )


class SearchPanel(QWidget):
    """The `Search` header, the query field and the results under the tree.

    Off by default, the query filters the tasks of the last reload by title as
    it is typed. With the content toggle on, Return searches the text of every
    task file instead. The panel only reports which task a result points at;
    selecting it in the table is left to the window.

    Args:
        margin: the outer margin the panel shares with the rest of the window.
        parent: the widget the panel belongs to.
    """

    task_activated = Signal(object)

    def __init__(self, margin: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # the tasks of the last reload, each with the title of its category
        self.entries: list[tuple[listing.TaskEntry, str]] = []
        self._directory = Path.cwd()
        self._base_title = ""
        # None until a content search runs for the current text
        self._content_hits: list[listing.ContentHit] | None = None

        self.search_results = _SearchResults()
        self.search_results.setColumnCount(4)
        self.search_results.setHeaderLabels(["Date", "Title", "Excerpt", "Category"])
        self.search_results.setHeaderHidden(True)
        self.search_results.setRootIsDecorated(False)
        self.search_results.setFrameShape(QFrame.Shape.NoFrame)
        results_header = self.search_results.header()
        results_header.setStretchLastSection(False)
        results_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        results_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        results_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        results_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.search_results.setColumnWidth(1, 150)
        self.search_results.setColumnWidth(2, 200)
        self.search_results.setColumnWidth(3, 65)
        results_header.setMinimumSectionSize(40)

        # the header shares the model of the results and shows only its first
        # section, renamed `Search`, so it looks like the `Directory` header
        self.search_header = QHeaderView(Qt.Orientation.Horizontal)
        self.search_header.setModel(self.search_results.model())
        for column in (1, 2, 3):
            self.search_header.setSectionHidden(column, True)
        self.search_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.search_header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.search_header.model().setHeaderData(
            0, Qt.Orientation.Horizontal, "Search", Qt.ItemDataRole.DisplayRole
        )

        self.search_content_checkbox = _icon_button(
            self.search_header, "Search in content", _draw_content, "ContentToggle"
        )
        self.search_content_checkbox.setCheckable(True)
        self.search_content_checkbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.search_content_checkbox.setChecked(False)
        self.search_content_checkbox.setIconSize(
            QSize(_HEADER_ICON_SIZE, _HEADER_ICON_SIZE)
        )
        self.search_header.geometriesChanged.connect(self._place_header_toggle)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_TITLE_PLACEHOLDER)
        self.search_input.setClearButtonEnabled(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(margin, 0, 0, margin)
        layout.setSpacing(0)
        layout.addWidget(self.search_header)
        layout.addWidget(self.search_input)
        layout.addWidget(self.search_results, 1)

        self.search_input.textChanged.connect(self._on_input_changed)
        self.search_input.returnPressed.connect(self._on_return_pressed)
        self.search_content_checkbox.toggled.connect(self._on_content_toggled)
        # only a click or an activation reaches the table, so typing and a
        # refill of the results never move its selection
        self.search_results.itemClicked.connect(self.activate_result)
        self.search_results.itemActivated.connect(self.activate_result)
        self.search_escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.search_input)
        self.search_escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.search_escape.activated.connect(self.search_input.clear)

    def set_entries(
        self,
        entries: list[tuple[listing.TaskEntry, str]],
        directory: Path,
        base_title: str,
    ) -> None:
        """Points the panel at the tasks of a reload and runs the query again.

        Args:
            entries: each listed task, closed ones included, with the title of
                its category.
            directory: the base folder a content search runs in.
            base_title: the category name of the tasks in the base folder.
        """
        self.entries = entries
        self._directory = directory
        self._base_title = base_title
        self._content_hits = None
        self._filter()

    def activate_first_result(self) -> None:
        """Reports the first result, as Return in the field asks."""
        item = self.search_results.topLevelItem(0)
        if item is not None:
            self.activate_result(item, 0)

    def activate_result(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        """Reports the task a result points at.

        Args:
            item: the result row that was clicked or activated.
            _column: the column of the row, unused.
        """
        self.task_activated.emit(Path(str(item.data(0, _PATH_ROLE))))

    def _content_mode(self) -> bool:
        return self.search_content_checkbox.isChecked()

    def _place_header_toggle(self) -> None:
        """Places the content toggle at the right end of the header, like the
        `Directory` header buttons."""
        header = self.search_header
        side = min(self.search_content_checkbox.sizeHint().height(), header.height())
        self.search_content_checkbox.resize(side, side)
        x = header.width() - _HEADER_BUTTON_MARGIN - side
        self.search_content_checkbox.move(x, (header.height() - side) // 2)

    def _on_input_changed(self, _text: str) -> None:
        if self._content_mode():
            # a content search runs only on Return, so new text drops old hits
            self.search_results.clear()
            self._content_hits = None
            self._refresh_content_message()
            return
        self._filter()

    def _on_content_toggled(self, checked: bool) -> None:
        self.search_results.clear()
        self._content_hits = None
        self.search_input.setPlaceholderText(
            _CONTENT_PLACEHOLDER if checked else _TITLE_PLACEHOLDER
        )
        self._refresh_content_message()
        if not checked:
            self._filter()

    def _refresh_content_message(self) -> None:
        """Shows the hint before a content search and `No results` after an
        empty one. The title filter shows no message."""
        if not self._content_mode():
            self.search_results.set_empty_message("")
        elif self._content_hits is None:
            self.search_results.set_empty_message("Press Enter to search content")
        elif not self._content_hits:
            self.search_results.set_empty_message("No results")
        else:
            self.search_results.set_empty_message("")

    def _on_return_pressed(self) -> None:
        if self._content_mode():
            self._run_content_search()
            return
        self.activate_first_result()

    def _run_content_search(self) -> None:
        query = self.search_input.text()
        if not query.strip():
            self.search_results.clear()
            self._content_hits = None
            self._refresh_content_message()
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            hits = listing.search_task_contents(self._directory, query)
            self._content_hits = hits
            self._show_content_results(hits)
            self._refresh_content_message()
        finally:
            QApplication.restoreOverrideCursor()

    def _add_result(
        self, path: Path, date: str, title: str, excerpt: str, category: str
    ) -> QTreeWidgetItem:
        """Adds one result row: date, title, excerpt and a dimmed category."""
        row = QTreeWidgetItem([date, helpers.readable_title(title), excerpt, category])
        row.setData(0, _PATH_ROLE, str(path))
        dim = self.search_results.palette().color(QPalette.ColorRole.PlaceholderText)
        row.setForeground(3, QBrush(dim))
        row.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for column in range(4):
            row.setToolTip(column, str(path))
        self.search_results.addTopLevelItem(row)
        return row

    def _show_content_results(self, hits: list[listing.ContentHit]) -> None:
        self.search_results.clear()
        # the excerpt column only exists in content mode
        self.search_results.setHeaderHidden(False)
        self.search_results.setColumnHidden(2, False)
        results_header = self.search_results.header()
        results_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        results_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.search_results.setColumnWidth(3, 65)

        for hit in hits:
            category = hit.category.name if hit.category is not None else self._base_title
            self._add_result(
                hit.task_path,
                hit.date.strftime(helpers.DATE_FORMAT),
                hit.title,
                hit.excerpt,
                category,
            )

    def _filter(self) -> None:
        """Refills the results with the tasks whose title matches the query,
        keeping the current result selected when it still matches."""
        if self._content_mode():
            self.search_results.clear()
            self._content_hits = None
            return
        self.search_results.set_empty_message("")
        self.search_results.setColumnHidden(2, True)
        self.search_results.setHeaderHidden(True)

        tasks = [entry for entry, _ in self.entries]
        found = {entry.file for entry in listing.search_tasks(tasks, self.search_input.text())}
        current = self.search_results.currentItem()
        kept = str(current.data(0, _PATH_ROLE)) if current is not None else None

        self.search_results.clear()
        restored: QTreeWidgetItem | None = None
        for entry, category in self.entries:
            if entry.file not in found:
                continue
            row = self._add_result(entry.file, _date_cell(entry), entry.title, "", category)
            if str(entry.file) == kept:
                restored = row

        if restored is not None:
            self.search_results.setCurrentItem(restored)
