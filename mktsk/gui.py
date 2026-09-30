from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import helpers, workers

_PATH_ROLE = Qt.ItemDataRole.UserRole

_ALL_TAB = "All"


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

        self.directory_tree = QTreeWidget()
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
        self.create_button = QPushButton("Create")
        form.addWidget(self.title_input, 1)
        form.addWidget(self.create_button)
        layout.addLayout(form)

        self.choose_button.clicked.connect(self.choose_directory)
        self.up_button.clicked.connect(self.go_up)
        self.refresh_button.clicked.connect(self.refresh)
        self.directory_tree.itemDoubleClicked.connect(self.open_directory)
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
        self.directory_tree.clear()
        if not self.current_directory.is_dir():
            self.tabs.clear()
            return

        self._reload_tree()
        self._reload_tasks()

    def _reload_tree(self) -> None:
        name = self.current_directory.name or str(self.current_directory)
        root = QTreeWidgetItem([name])
        for subdirectory in workers.list_subdirectories(self.current_directory):
            child = QTreeWidgetItem([subdirectory.name])
            child.setData(0, _PATH_ROLE, str(subdirectory))
            root.addChild(child)

        self.directory_tree.addTopLevelItem(root)
        root.setExpanded(True)

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

    def _new_listing(self) -> QListWidget:
        listing = QListWidget()
        listing.itemDoubleClicked.connect(self.open_item)
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
        item.setData(_PATH_ROLE, str(entry.file))
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

    def open_item(self, item: QListWidgetItem) -> None:
        path = item.data(_PATH_ROLE)
        if path:
            self.open_with_default_app(Path(path))

    def open_with_default_app(self, path: Path) -> None:
        try:
            helpers.open_file(path)
        except OSError as error:
            QMessageBox.warning(self, "mktsk", f"Could not open file: {error}")

    def create_task(self) -> None:
        raw_title = self.title_input.text()
        if not raw_title.strip():
            QMessageBox.critical(self, "mktsk", "Invalid task description.")
            return

        try:
            result = workers.open_or_create_task(self.current_directory, raw_title)
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
