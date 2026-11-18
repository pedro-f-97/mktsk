"""The bar of actions under the selected task row."""


from PySide6.QtGui import (
    QPalette,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLayout,
    QMenu,
    QToolButton,
    QWidget,
)

from mktsk import parsing

from .icons import (
    _draw_bell,
    _draw_close,
    _draw_folder,
    _draw_pencil,
    _draw_plus,
    _draw_reopen,
    _draw_state,
    _icon_button,
    _stroked_icon,
)

_ACTION_BAR_PADDING = 4

# the states the change-state action offers: `closed` only comes from closing
# the task, which is a different operation
_OFFERED_STATES = tuple(state for state in parsing.STATES if state != "closed")


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
        self.state_button = _icon_button(
            self, "Change the state of this task", _draw_state, "ChangeState"
        )
        self.close_button = _icon_button(self, "Close this task", _draw_close, "CloseTask")
        # the reminders button speaks to the reminders of the task rather than
        # to the task itself, and stands only when the window carries a
        # scheduler behind them, so a run without a tray never offers it
        self.reminders_button = _icon_button(
            self, "Reminders", _draw_bell, "Reminders"
        )
        self.reminders_menu = QMenu(self.reminders_button)
        self.reminders_menu.addAction("Add reminder...")
        self.reminders_menu.addAction("Reminders...")
        self.reminders_button.setMenu(self.reminders_menu)
        # the menu opens from the click rather than from the press, so the
        # button never waits for a menu that the click itself has to close
        self.reminders_button.clicked.connect(self._open_reminders_menu)
        self._reminders_available = False
        self._reopening = False
        # the resume button is the one set_reopening turns into the reopen
        # action, so what it starts with is what puts back
        self._resume_icon = self.resume_button.icon()
        self._resume_tooltip = self.resume_button.toolTip()
        self.state_menu = QMenu(self.state_button)
        for offered in _OFFERED_STATES:
            self.state_menu.addAction(offered)
        self.state_button.setMenu(self.state_menu)
        # the menu opens from the click rather than from the press, so the
        # button never waits for a menu that the click itself has to close
        self.state_button.clicked.connect(self._open_state_menu)
        # the archive button closes the task, so it stands last of the bar,
        # after the reminders button when it is shown; the other buttons keep
        # their order
        for button in self.buttons()[:-1]:
            layout.addWidget(button)
        layout.addWidget(self.reminders_button)
        layout.addWidget(self.close_button)
        self._update_reminder_buttons()
        # the stretch keeps the surplus of the bar away from the buttons, so
        # they pack to the left edge even when only the reopen one is shown
        layout.addStretch()

    def _open_state_menu(self) -> None:
        """Opens the menu of states under the button that carries it."""
        self.state_menu.popup(
            self.state_button.mapToGlobal(self.state_button.rect().bottomLeft())
        )

    def _open_reminders_menu(self) -> None:
        """Opens the reminders menu under the button that carries it."""
        self.reminders_menu.popup(
            self.reminders_button.mapToGlobal(self.reminders_button.rect().bottomLeft())
        )

    def buttons(self) -> tuple[QToolButton, ...]:
        """Returns the five action buttons, in order."""
        return (
            self.open_button,
            self.resume_button,
            self.rename_button,
            self.state_button,
            self.close_button,
        )

    def reminder_buttons(self) -> tuple[QToolButton, ...]:
        """Returns the reminders button, alone."""
        return (self.reminders_button,)

    def set_reminders_available(self, available: bool) -> None:
        """Offers the reminder buttons only when a scheduler stands behind them.

        Args:
            available: whether the window carries a reminder scheduler.
        """
        self._reminders_available = available
        self._update_reminder_buttons()

    def _update_reminder_buttons(self) -> None:
        """Shows the reminders button on an open task when a scheduler exists."""
        visible = self._reminders_available and not self._reopening
        self.reminders_button.setVisible(visible)

    def set_reopening(self, reopening: bool) -> None:
        """Shows only the reopen action for a closed task.

        The resume button turns into reopen; the actions that need a folder hide.

        Args:
            reopening: True when the selected row holds a closed task.
        """
        self._reopening = reopening
        for button in (
            self.open_button,
            self.rename_button,
            self.state_button,
            self.close_button,
        ):
            button.setVisible(not reopening)
        self._update_reminder_buttons()

        if reopening:
            self.resume_button.setIcon(
                _stroked_icon(
                    self.resume_button.palette().color(
                        QPalette.ColorRole.ButtonText
                    ),
                    _draw_reopen,
                )
            )
            self.resume_button.setToolTip("Reopen this task")
        else:
            self.resume_button.setIcon(self._resume_icon)
            self.resume_button.setToolTip(self._resume_tooltip)
