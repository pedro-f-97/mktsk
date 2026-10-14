"""The main window, over the task logic the CLI uses."""

import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QCloseEvent, QPalette, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mktsk import files, helpers, listing, standards, state, tasks

from .icons import _draw_choose, _draw_refresh, _draw_up, _icon_button
from .tasklist import (
    _AGE_ROLE,
    _COUNT_ROLE,
    _ENTRY_ROLE,
    _STATE_ROLE,
    TaskListing,
    TaskPanel,
    _relative_age,
)
from .tree import _PATH_ROLE, _CategoryTree

_ALL_TAB = "All"
_CLOSED_TAB = "Closed"

# the outer margin the left path row, the tab bar and the bottom bar share, so
# the two panes line up on a single grid
_MARGIN = 6


class MainWindow(QMainWindow):
    """Desktop interface over the CLI task logic."""

    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or QSettings("mktsk", "mktsk")
        self._sorts: dict[str, tuple[int, bool]] = {}
        last_path = self.settings.value("last_path", str(Path.cwd()))
        self.current_directory = Path(str(last_path))
        self.setWindowTitle("mktsk")
        self.setMinimumSize(640, 420)
        self._build_ui()
        self.navigate_to(self.current_directory)

    def _build_ui(self) -> None:
        # the widgets are built in the order the old bar used, so the default
        # tab order is unchanged; the two panels are assembled around them
        self.path_label = QLabel()
        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.directory_tree = _CategoryTree()
        self.directory_tree.set_header_label("Directory")
        self.tabs = QTabWidget()
        self.choose_button = _icon_button(
            self.directory_tree.header(), "Choose...", _draw_choose, "Choose"
        )
        self.up_button = _icon_button(
            self.directory_tree.header(), "Up", _draw_up, "Up"
        )
        self.refresh_button = _icon_button(
            self.tabs, "Refresh", _draw_refresh, "Refresh"
        )
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

        self.directory_tree.set_navigation_buttons(self.choose_button, self.up_button)

        self.path_row = QWidget()
        path_layout = QHBoxLayout(self.path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.path_label, 1)

        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        left_layout.setSpacing(0)
        left_layout.addWidget(self.path_row)
        left_layout.addWidget(self.directory_tree)

        self.tabs.setCornerWidget(self.refresh_button, Qt.Corner.TopRightCorner)

        self.bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self.title_input, 1)
        bottom_layout.addWidget(self.target_label)
        bottom_layout.addWidget(self.create_button)

        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.tabs, 1)
        right_layout.addWidget(self.bottom_bar)

        self.splitter = QSplitter()
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(1, 2)
        self.setCentralWidget(self.splitter)

        self.choose_button.clicked.connect(self.choose_directory)
        self.up_button.clicked.connect(self.go_up)
        self.refresh_button.clicked.connect(self.refresh)
        self.directory_tree.itemDoubleClicked.connect(self.open_directory)
        self.directory_tree.itemSelectionChanged.connect(self._sync_creation_target)
        self.directory_tree.category_requested.connect(self.new_category)
        self.title_input.returnPressed.connect(self.create_task)
        self.create_button.clicked.connect(self.create_task)
        self.splitter.splitterMoved.connect(self._update_path_label)

        # the old bar's focus order, kept by hand because the panels now hold
        # the same widgets in a different tree
        self.setTabOrder(self.choose_button, self.up_button)
        self.setTabOrder(self.up_button, self.refresh_button)
        self.setTabOrder(self.refresh_button, self.directory_tree)
        self.setTabOrder(self.directory_tree, self.tabs)
        self.setTabOrder(self.tabs, self.title_input)
        self.setTabOrder(self.title_input, self.create_button)

    def _align_path_row(self) -> None:
        """Squares the path row off to the height of the tab bar it lines up with."""
        self.path_row.setFixedHeight(self.tabs.tabBar().sizeHint().height())

    def _update_path_label(self) -> None:
        """Shows the current directory, elided to the room the row has."""
        path = str(self.current_directory)
        metrics = self.path_label.fontMetrics()
        self.path_label.setText(
            metrics.elidedText(
                path, Qt.TextElideMode.ElideMiddle, self.path_label.width()
            )
        )
        self.path_label.setToolTip(path)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_path_label()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._align_path_row()
        self._update_path_label()

    def navigate_to(self, directory: Path) -> None:
        directory = directory.resolve()
        if not directory.is_dir():
            directory = Path.cwd()
        self.current_directory = directory
        self._update_path_label()
        self._sorts.clear()
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
        for subdirectory in listing.list_subdirectories(self.current_directory):
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
        # one day for the whole listing, so a refresh that runs as the date turns
        # does not date half of the tasks to yesterday
        today = datetime.datetime.now().astimezone().date()
        sections = self._sections()
        active = self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.count() else ""

        self.tabs.clear()

        every = self._new_listing(_ALL_TAB)
        shut = self._new_listing(_CLOSED_TAB)
        closed_here = False

        for title, group in sections:
            standing = [entry for entry in group.entries if entry.state != "closed"]
            archived = [entry for entry in group.entries if entry.state == "closed"]

            if standing:
                self._add_heading(every, title)
                for entry in standing:
                    self._add_task(every, entry, today)

            if archived:
                self._add_heading(shut, title)
                for entry in archived:
                    self._add_task(shut, entry, today)
                closed_here = True

        self._add_tab(_ALL_TAB, every)

        for title, group in sections:
            standing = [entry for entry in group.entries if entry.state != "closed"]
            if not standing:
                continue

            tab = self._new_listing(title)
            for entry in standing:
                self._add_task(tab, entry, today)
            self._add_tab(title, tab)

        if closed_here:
            self._add_tab(_CLOSED_TAB, shut)

        self._select_tab(active)

    def _sections(self) -> list[tuple[str, listing.TaskGroup]]:
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
            for group in listing.find_task_groups(self.current_directory)
        ]

    def _base_title(self) -> str:
        """Returns the title of the tab for the tasks of the current directory."""
        return self.current_directory.name or str(self.current_directory)

    def _new_listing(self, title: str) -> TaskListing:
        tab = TaskListing()
        tab.open_requested.connect(self.open_task)
        tab.resume_requested.connect(self.resume_task)
        tab.rename_requested.connect(self.rename_task)
        tab.state_requested.connect(self.change_state)
        tab.close_requested.connect(self.close_task)
        tab.order_changed.connect(
            lambda column, descending, name=title: self._remember_sort(
                name, column, descending
            )
        )
        return tab

    def _remember_sort(self, title: str, column: int, descending: bool) -> None:
        """Keeps the column and the direction a tab was last sorted by."""
        self._sorts[title] = (column, descending)

    def _add_tab(self, title: str, tab: TaskListing) -> None:
        if title in self._sorts:
            tab.set_sort(*self._sorts[title])
        tab.fit_task_column()
        self.tabs.addTab(TaskPanel(tab), title)

    def _select_tab(self, title: str) -> None:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.tabs.setCurrentIndex(index)
                return

        self.tabs.setCurrentIndex(0)

    def _add_heading(self, tab: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        tab.addItem(item)

    def _add_task(
        self, tab: QListWidget, entry: listing.TaskEntry, today: datetime.date
    ) -> None:
        date = entry.date.strftime(helpers.DATE_FORMAT)
        item = QListWidgetItem(f"{date}  {helpers.readable_title(entry.title)}")
        item.setData(_ENTRY_ROLE, entry)
        item.setData(_STATE_ROLE, entry.state)
        item.setData(_COUNT_ROLE, str(entry.interventions))
        item.setData(_AGE_ROLE, _relative_age(entry.last_activity, today))
        item.setToolTip(str(entry.file))
        tab.addItem(item)

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
            category = files.create_category(self.current_directory, raw_name)
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.refresh()
        self.directory_tree.select_subdirectory(category)

    def open_task(self, entry: listing.TaskEntry) -> None:
        """Reveals the folder of a task with the file manager.

        Args:
            entry: the selected task.
        """
        self.open_with_default_app(entry.file.parent)

    def resume_task(self, entry: listing.TaskEntry) -> None:
        """Adds a dated section to a task and opens it, reopening it if closed.

        The task is resumed where it is, which is not necessarily the current
        directory. A row that holds an archive is reopened: the archive is
        extracted, the task resumed and the archive deleted, and the listing
        is refreshed either way, because the row now carries the count and the
        age the new intervention has changed.

        Args:
            entry: the selected task.
        """
        try:
            if standards.is_task_archive(entry.file.name):
                result = tasks.reopen_task(entry.file.parent, entry.title)
            else:
                result = tasks.resume_task(entry.file.parent, entry.title)
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.refresh()
        self.open_with_default_app(result.file)

    def rename_task(self, entry: listing.TaskEntry) -> None:
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
            tasks.rename_task(entry.file.parent, entry.title, raw_title)
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.refresh()

    def change_state(self, entry: listing.TaskEntry, new_state: str) -> None:
        """Sets the state of a task by hand, and refreshes the list.

        The task is changed where it lives, which is not necessarily the
        current directory, and nothing is opened: picking a state is not
        working on the task.

        Args:
            entry: the selected task.
            new_state: the state the user chose.
        """
        try:
            state.set_state(entry.file, new_state)
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.refresh()

    def close_task(self, entry: listing.TaskEntry) -> None:
        """Archives a task folder into a zip.

        The folder becomes a zip beside where it stood, and the .md inside the
        zip carries the closed event. The folder is only gone once the archive
        is verified, and nothing is opened: the task is over.

        Args:
            entry: the selected task.
        """
        try:
            tasks.close_task(entry.file.parent, entry.title)
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
            result = tasks.open_or_create_task(self.creation_directory(), raw_title)
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.open_with_default_app(result.file)
        self.refresh()
        self.title_input.clear()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.setValue("last_path", str(self.current_directory))
        super().closeEvent(event)
