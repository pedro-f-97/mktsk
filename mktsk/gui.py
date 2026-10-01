from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QPointF,
    QRect,
    QRectF,
    QSettings,
    QSize,
    Qt,
    Signal,
    SignalInstance,
)
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QIcon,
    QImage,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import helpers, workers

_PATH_ROLE = Qt.ItemDataRole.UserRole
_ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1

_ALL_TAB = "All"

_ACTION_BAR_PADDING = 4
_HEADER_BUTTON_MARGIN = 4
_HEADER_ICON_SIZE = 12
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
        self.header_button.clicked.connect(lambda: self.category_requested.emit())
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

    def selected_entry(self) -> workers.TaskEntry | None:
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


class MainWindow(QMainWindow):
    """Desktop interface over the CLI task logic."""

    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or QSettings("mktsk", "mktsk")
        last_path = self.settings.value("last_path", str(Path.cwd()))
        self.current_directory = Path(str(last_path))
        self.setWindowTitle("mktsk")
        self.setMinimumSize(640, 420)
        self._build_ui()
        self.navigate_to(self.current_directory)

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        bar = QHBoxLayout()
        self.path_label = QLabel()
        self.choose_button = QPushButton("Choose...")
        self.up_button = QPushButton("Up")
        self.refresh_button = QPushButton("Refresh")
        bar.addWidget(self.path_label, 1)
        bar.addWidget(self.choose_button)
        bar.addWidget(self.up_button)
        bar.addWidget(self.refresh_button)
        layout.addLayout(bar)

        self.directory_tree = _CategoryTree()
        self.directory_tree.setHeaderLabel("Directory")
        self.directory_tree.setMinimumWidth(140)

        self.tabs = QTabWidget()

        splitter = QSplitter()
        splitter.addWidget(self.directory_tree)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        form = QHBoxLayout()
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Task title")
        self.target_label = QLabel()
        # the hint goes where the task is created, in the font it already uses,
        # so it adds no height of its own and only the colour tells it apart
        self.target_label.setWordWrap(False)
        hint = self.target_label.palette()
        hint.setColor(
            QPalette.ColorRole.WindowText,
            hint.color(QPalette.ColorRole.PlaceholderText),
        )
        self.target_label.setPalette(hint)
        self.target_label.hide()
        self.create_button = QPushButton("Create")
        form.addWidget(self.title_input, 1)
        form.addWidget(self.target_label)
        form.addWidget(self.create_button)
        layout.addLayout(form)

        self.choose_button.clicked.connect(self.choose_directory)
        self.up_button.clicked.connect(self.go_up)
        self.refresh_button.clicked.connect(self.refresh)
        self.directory_tree.itemDoubleClicked.connect(self.open_directory)
        self.directory_tree.itemSelectionChanged.connect(self._sync_creation_target)
        self.directory_tree.category_requested.connect(self.new_category)
        self.title_input.returnPressed.connect(self.create_task)
        self.create_button.clicked.connect(self.create_task)

    def navigate_to(self, directory: Path) -> None:
        directory = directory.resolve()
        if not directory.is_dir():
            directory = Path.cwd()
        self.current_directory = directory
        self.path_label.setText(str(directory))
        self.refresh()

    def refresh(self) -> None:
        if not self.current_directory.is_dir():
            self.directory_tree.clear()
            self.target_label.hide()
            self.tabs.clear()
            return

        self._reload_tree()
        self._sync_creation_target()
        self._reload_tasks()

    def _reload_tree(self) -> None:
        # the selection is read before the clear, which takes it with it
        selected = self._selected_directory()
        self.directory_tree.clear()
        name = self.current_directory.name or str(self.current_directory)
        root = QTreeWidgetItem([name])
        for subdirectory in workers.list_subdirectories(self.current_directory):
            child = QTreeWidgetItem([subdirectory.name])
            child.setData(0, _PATH_ROLE, str(subdirectory))
            root.addChild(child)

        self.directory_tree.addTopLevelItem(root)
        root.setExpanded(True)

        # a category that is no longer there is dropped, and the current
        # directory takes over as the creation target
        if selected is not None:
            self.directory_tree.select_subdirectory(selected)

    def _selected_directory(self) -> Path | None:
        """Returns the subdirectory selected in the tree, or None when the root
        or nothing is selected."""
        item = self.directory_tree.currentItem()
        path = item.data(0, _PATH_ROLE) if item else None
        return Path(path) if path else None

    def creation_directory(self) -> Path:
        """Returns the directory a new task is created in.

        A subdirectory selected in the tree is the target, so a task lands in a
        category without having to enter it. With the root, or nothing,
        selected the current directory is the target.

        Returns:
            The directory to create the task in.
        """
        return self._selected_directory() or self.current_directory

    def _sync_creation_target(self) -> None:
        """Points the target line at the directory a new task would land in."""
        target = self.creation_directory()

        if target == self.current_directory:
            self.target_label.hide()
            return

        # the path label beside it already names the base directory, so the name
        # of the category says it all and the full path stays in the tooltip
        self.target_label.setText(f"New tasks in {target.name}")
        self.target_label.setToolTip(str(target))
        self.target_label.show()

    def _reload_tasks(self) -> None:
        sections = self._sections()
        active = self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.count() else ""

        self.tabs.clear()

        every = self._new_listing()
        for title, group in sections:
            self._add_heading(every, title)
            for entry in group.entries:
                self._add_task(every, entry)
        self._add_tab(_ALL_TAB, every)

        for title, group in sections:
            listing = self._new_listing()
            for entry in group.entries:
                self._add_task(listing, entry)
            self._add_tab(title, listing)

        self._select_tab(active)

    def _sections(self) -> list[tuple[str, workers.TaskGroup]]:
        """Pairs every task group with the title of its tab.

        Returns:
            The tasks of the current directory first, named after the directory
            itself, then the tasks of each subdirectory in alphabetical order.
        """
        return [
            (
                self._base_title() if group.category is None else group.category.name,
                group,
            )
            for group in workers.find_task_groups(self.current_directory)
        ]

    def _base_title(self) -> str:
        """Returns the title of the tab for the tasks of the current directory."""
        return self.current_directory.name or str(self.current_directory)

    def _new_listing(self) -> TaskListing:
        listing = TaskListing()
        listing.open_requested.connect(self.open_task)
        listing.resume_requested.connect(self.resume_task)
        listing.rename_requested.connect(self.rename_task)
        return listing

    def _add_tab(self, title: str, listing: QListWidget) -> None:
        self.tabs.addTab(listing, title)

    def _select_tab(self, title: str) -> None:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.tabs.setCurrentIndex(index)
                return

        self.tabs.setCurrentIndex(0)

    def _add_heading(self, listing: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        listing.addItem(item)

    def _add_task(self, listing: QListWidget, entry: workers.TaskEntry) -> None:
        date = entry.date.strftime(workers.DATE_FORMAT)
        item = QListWidgetItem(f"{date}  {helpers.readable_title(entry.title)}")
        item.setData(_ENTRY_ROLE, entry)
        item.setToolTip(str(entry.file))
        listing.addItem(item)

    def choose_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose directory", str(self.current_directory)
        )
        if selected:
            self.navigate_to(Path(selected))

    def go_up(self) -> None:
        parent = self.current_directory.parent
        if parent != self.current_directory:
            self.navigate_to(parent)

    def open_directory(self, item: QTreeWidgetItem, _column: int) -> None:
        path = item.data(0, _PATH_ROLE)
        if path:
            self.navigate_to(Path(path))

    def new_category(self) -> None:
        """Asks for a name and creates the category in the current directory.

        A category that is already there is not created again, it is selected,
        and a new one is left selected too, so it becomes the target of the next
        task without having to enter it.
        """
        raw_name, accepted = QInputDialog.getText(
            self, "New category", "Name", QLineEdit.EchoMode.Normal
        )

        if not accepted or not raw_name.strip():
            return

        try:
            category = workers.create_category(self.current_directory, raw_name)
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.refresh()
        self.directory_tree.select_subdirectory(category)

    def open_task(self, entry: workers.TaskEntry) -> None:
        """Reveals the folder of a task with the file manager.

        Args:
            entry: the selected task.
        """
        self.open_with_default_app(entry.file.parent)

    def resume_task(self, entry: workers.TaskEntry) -> None:
        """Adds a dated section to a task and opens it.

        The task is resumed where it is, which is not necessarily the current
        directory.

        Args:
            entry: the selected task.
        """
        try:
            result = workers.resume_task(entry.file.parent, entry.title)
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.open_with_default_app(result.file)

    def rename_task(self, entry: workers.TaskEntry) -> None:
        """Renames a task, keeping the date it was created on.

        Args:
            entry: the selected task.
        """
        raw_title, accepted = QInputDialog.getText(
            self,
            "Rename task",
            "Title",
            QLineEdit.EchoMode.Normal,
            helpers.readable_title(entry.title),
        )

        if not accepted or not raw_title.strip():
            return

        try:
            workers.rename_task(entry.file.parent, entry.title, raw_title)
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.refresh()

    def open_with_default_app(self, path: Path) -> None:
        try:
            helpers.open_file(path)
        except OSError as error:
            QMessageBox.warning(self, "mktsk", str(error))

    def create_task(self) -> None:
        raw_title = self.title_input.text()
        if not raw_title.strip():
            QMessageBox.critical(self, "mktsk", "Invalid task description.")
            return

        try:
            result = workers.open_or_create_task(self.creation_directory(), raw_title)
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.open_with_default_app(result.file)
        self.refresh()
        self.title_input.clear()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.setValue("last_path", str(self.current_directory))
        super().closeEvent(event)


def main() -> int:  # pragma: no cover
    """Runs the desktop interface."""
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
