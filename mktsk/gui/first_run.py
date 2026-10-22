"""The first-run flow the GUI runs before the main window opens.

The base folder lives in the config file the CLI also reads, so the GUI asks
for it here rather than keeping a path of its own. Every prompt is a plain
`QMessageBox`, and the setup dialog is the only place that writes the config,
through `run_setup`, the same routine the CLI uses.
"""

import enum
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mktsk import config


class MissingChoice(enum.Enum):
    """What to do about a saved base folder that is gone."""

    RETRY = "retry"
    CHOOSE = "choose"
    CANCEL = "cancel"


def ask_start_setup(parent: QWidget | None = None) -> bool:
    """Asks whether to start the setup when no folder is configured.

    Args:
        parent: the widget the question is shown over.

    Returns:
        True when the user chose to start the setup.
    """
    answer = QMessageBox.question(
        parent,
        "mktsk",
        "mktsk is not configured yet. Start setup?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


def ask_missing_folder(
    parent: QWidget | None = None, path: Path | None = None
) -> MissingChoice:
    """Asks what to do about a saved base folder that no longer exists.

    Args:
        parent: the widget the question is shown over.
        path: the folder the config names, shown so it can be recognised.

    Returns:
        Retry to resolve the saved folder again, choose to run the setup, or
        cancel to close without a window.
    """
    message = QMessageBox(parent)
    message.setIcon(QMessageBox.Icon.Warning)
    message.setWindowTitle("mktsk")
    message.setText(f"The saved base folder does not exist:\n{path}")
    retry = message.addButton("Retry", QMessageBox.ButtonRole.AcceptRole)
    choose = message.addButton(
        "Choose another folder", QMessageBox.ButtonRole.AcceptRole
    )
    message.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    message.exec()

    clicked = message.clickedButton()

    if clicked is retry:
        return MissingChoice.RETRY
    if clicked is choose:
        return MissingChoice.CHOOSE
    return MissingChoice.CANCEL


class SetupDialog(QDialog):
    """Asks for the base folder and up to two categories."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("mktsk setup")
        self.base_folder: Path | None = None

        self.base_input = QLineEdit()
        self.browse_button = QPushButton("Browse...")
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.base_input, 1)
        folder_row.addWidget(self.browse_button)

        # only two categories exist, so there is no way to ask for a third
        self.category_inputs = [QLineEdit(), QLineEdit()]
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Base folder"))
        layout.addLayout(folder_row)
        layout.addWidget(QLabel("Category 1 (optional)"))
        layout.addWidget(self.category_inputs[0])
        layout.addWidget(QLabel("Category 2 (optional)"))
        layout.addWidget(self.category_inputs[1])
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        self.browse_button.clicked.connect(self.browse)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

    def browse(self) -> None:
        """Fills the base folder with the folder picked in the native dialog."""
        selected = QFileDialog.getExistingDirectory(
            self, "Choose base folder", self.base_input.text().strip()
        )

        if selected:
            self.base_input.setText(selected)

    def _accept(self) -> None:
        """Creates the folders and saves the config, or shows why it did not."""
        categories = [
            field.text() for field in self.category_inputs if field.text().strip()
        ]

        try:
            self.base_folder = config.run_setup(self.base_input.text(), categories)
        except (OSError, ValueError) as error:
            # run_setup validates and creates before it writes, so the saved
            # config is still the one it was
            self.error_label.setText(str(error))
            self.error_label.show()
            return

        self.accept()


def run_setup_dialog(parent: QWidget | None = None) -> Path | None:
    """Shows the setup dialog and returns the folder it saved.

    Args:
        parent: the widget the dialog is shown over.

    Returns:
        The base folder the setup saved, or None when the user cancelled.
    """
    dialog = SetupDialog(parent)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.base_folder

    return None


def ensure_base_folder(parent: QWidget | None = None) -> Path | None:
    """Makes sure a usable base folder is configured before the window opens.

    A folder that was never configured offers the setup, and one that is gone
    offers to retry, choose another folder or cancel. A cancelled setup after
    a missing folder asks about the missing folder again, because the saved
    one is still gone; a cancelled setup when nothing was configured gives
    up, because there is nothing to go back to.

    Args:
        parent: the widget the prompts are shown over.

    Returns:
        The base folder to open the window in, or None when the user gave up.
    """
    while True:
        resolved = config.resolve_base_folder()

        if resolved.state is config.BaseFolderState.OK:
            return resolved.path

        if resolved.state is config.BaseFolderState.NOT_CONFIGURED:
            if not ask_start_setup(parent):
                return None
            return run_setup_dialog(parent)

        choice = ask_missing_folder(parent, resolved.path)

        if choice is MissingChoice.CANCEL:
            return None
        if choice is MissingChoice.RETRY:
            continue

        chosen = run_setup_dialog(parent)

        if chosen is not None:
            return chosen
