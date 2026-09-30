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
    QVBoxLayout,
    QWidget,
)

from . import helpers, workers

_PATH_ROLE = Qt.ItemDataRole.UserRole
_IS_DIR_ROLE = Qt.ItemDataRole.UserRole + 1


class MainWindow(QMainWindow):
    """Desktop interface over the CLI task logic."""

    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or QSettings("mktsk", "mktsk")
        last_path = self.settings.value("last_path", str(Path.cwd()))
        self.current_directory = Path(str(last_path))
        self.setWindowTitle("mktsk")
        self.setMinimumSize(480, 360)
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

        self.file_list = QListWidget()
        layout.addWidget(self.file_list)

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
        self.file_list.itemDoubleClicked.connect(self.open_item)
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
        self.file_list.clear()
        if not self.current_directory.is_dir():
            return

        tasks = []
        other = []
        for entry in self.current_directory.iterdir():
            if entry.is_dir() and workers.is_task_folder(entry.name):
                tasks.append(entry)
            else:
                other.append(entry)

        for heading, group in (("Tasks", tasks), ("Other", other)):
            if not group:
                continue

            self._add_heading(heading)
            for entry in sorted(group, key=self._sort_key):
                self._add_entry(entry)

    def _add_heading(self, text: str) -> None:
        item = QListWidgetItem(text)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.file_list.addItem(item)

    def _add_entry(self, entry: Path) -> None:
        label = f"{entry.name}/" if entry.is_dir() else entry.name
        item = QListWidgetItem(label)
        item.setData(_PATH_ROLE, str(entry))
        item.setData(_IS_DIR_ROLE, entry.is_dir())
        self.file_list.addItem(item)

    def _sort_key(self, path: Path) -> tuple[bool, str]:
        return (not path.is_dir(), path.name.lower())

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

    def open_item(self, item: QListWidgetItem) -> None:
        path = Path(item.data(_PATH_ROLE))
        if item.data(_IS_DIR_ROLE):
            self.navigate_to(path)
        else:
            self.open_with_default_app(path)

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