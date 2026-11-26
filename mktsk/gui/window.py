"""The main window, over the task logic the CLI uses."""

import datetime
from pathlib import Path
from typing import cast

from PySide6.QtCore import (
    QByteArray,
    QLockFile,
    QMimeData,
    QPoint,
    QSettings,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QKeySequence,
    QPalette,
    QResizeEvent,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedLayout,
    QStyleFactory,
    QTabWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mktsk import config, files, helpers, listing, standards, state, tasks

from .actionbar import _OFFERED_STATES
from .app_icon import app_icon, set_app_identity
from .icons import (
    _SMALL_ICON_SIZE,
    _draw_choose,
    _draw_cross,
    _draw_filter,
    _draw_refresh,
    _draw_up,
    _icon_button,
)
from .panetoggle import PaneToggle
from .preview import PreviewPanel
from .reminders_scheduler import ReminderScheduler
from .reminders_ui import RemindersList
from .resize_grips import ResizeGrips
from .search import SearchPanel
from .selection import _DirectorySelectionStyle, _UnifiedSelectionDelegate
from .tasklist import TaskListing, TaskPanel
from .taskrow import (
    _AGE_ROLE,
    _CATEGORY_ROLE,
    _COUNT_ROLE,
    _ENTRY_ROLE,
    _STATE_ROLE,
    _relative_age,
    _state_column_min_width,
)
from .titlebar import TitleBar
from .tray import TrayController
from .tree import (
    _HEADER_ICON_SIZE,
    _PATH_ROLE,
    _CategoryTree,
)
from .windows_snap import enable_snap_styles, handle_native_event

_ALL_TAB = "All"
_CLOSED_TAB = "Closed"

# column index of the State cell in the task row header (taskrow._HEADINGS)
STATE_COLUMN = 3
# room kept between the filter button and the State/Interventions resize handle
_STATE_FILTER_MARGIN = 6

# the title of the left Directory header, kept in one place so the tree can hide
# it when the header is too narrow to hold it before the buttons
_DIRECTORY_HEADER = "Directory"

# the title the same header carries while the reminders panel takes the place
# of the tree
_REMINDERS_HEADER = "Reminders"

# the outer margin the left Directory header, the tab bar and the bottom bar
# share, so the two panes line up on a single grid
_MARGIN = 6

# the side rail is as wide as the Refresh button it carries plus this padding,
# so its width follows the style rather than a pixel figure of its own
_RAIL_PADDING = 2

# how many files a drop that left some out names in the warning about it; the
# rest are counted in a line of their own, so a long list never fills it
_MAX_SKIPPED_NAMED = 10

# the key the window keeps its size and position under; the splitters keep
# theirs under the keys `_splitters` gives them
_GEOMETRY_KEY = "window/geometry"


def _skipped_message(skipped: list[tuple[Path, str]]) -> str:
    """Builds the warning about the files a drop did not move.

    Names at most `_MAX_SKIPPED_NAMED` of them and counts the rest.

    Args:
        skipped: each file that was not moved, with the reason why.

    Returns:
        The text of the warning.
    """
    lines = ["Some files were not moved into the task folder:"]

    for path, reason in skipped[:_MAX_SKIPPED_NAMED]:
        lines.append(f"{path}: {reason}")

    remaining = len(skipped) - _MAX_SKIPPED_NAMED
    if remaining > 0:
        lines.append(f"and {remaining} more")

    return "\n".join(lines)


class MainWindow(QMainWindow):
    """Desktop interface over the CLI task logic."""

    # the tray controller, when the platform offers a tray; set from the
    # entry point once the window exists
    tray_controller: TrayController | None = None
    # the instance lock, kept alive for the whole run and released on quit
    _instance_lock: QLockFile | None = None

    def __init__(
        self, settings: QSettings | None = None, base_folder: Path | None = None
    ) -> None:
        super().__init__()
        self.settings = settings or QSettings("mktsk", "mktsk")
        self._sorts: dict[str, tuple[int, bool]] = {}
        # the width the left pane had before the toggle bar collapsed it, and
        # the split the splitter opened with, to fall back on when a collapse
        # came from dragging the handle rather than from the bar
        self._left_width: int | None = None
        self._initial_left_width: int | None = None
        # whether a real quit has been requested, so a close event that comes
        # after it is accepted instead of hiding the window to the tray
        self._quitting = False
        # whether the Aero Snap window styles have been applied to the native
        # window; only done once, after the first show
        self._snap_styles_applied = False
        # the reminder scheduler, created with the tray; set from the entry
        # point once the window exists
        self.reminder_scheduler: ReminderScheduler | None = None
        # the reminders panel and its list, built when a scheduler is attached
        self.reminders_panel: QWidget | None = None
        self.reminders_list: RemindersList | None = None
        # the folder the first-run flow resolved lives in the shared config
        # file, so it is handed in rather than read from QSettings
        self.current_directory = base_folder or Path.cwd()
        self.setWindowTitle("mktsk")
        # the window carries the icon the application draws for itself
        self.setWindowIcon(app_icon())
        # the taskbar shows the application by the identity it sets here
        set_app_identity()
        self.setMinimumSize(640, 420)
        # the native frame is replaced by the title bar and the edge grips
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        # the window takes in a drag of files, which lands in the folder of
        # the selected task
        self.setAcceptDrops(True)
        self._build_ui()
        self._restore_state()
        self.navigate_to(self.current_directory)

    def _build_ui(self) -> None:
        # the widgets are built in the order the old bar used, so the default
        # tab order is unchanged; the two panels are assembled around them
        self.path_label = QLabel()
        # the path sits under the header and over the tree, so it takes the
        # tree's Base background rather than the Window one, and follows it in
        # a dark mode through the palette alone
        self.path_label.setAutoFillBackground(True)
        self.path_label.setBackgroundRole(QPalette.ColorRole.Base)
        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.directory_tree = _CategoryTree()
        self.directory_tree.set_header_label(_DIRECTORY_HEADER)
        self.directory_tree.setFrameShape(QFrame.Shape.NoFrame)
        self.directory_tree.setItemDelegate(
            _UnifiedSelectionDelegate(self.directory_tree, rail_at_left_edge=True)
        )
        # the native fill of the selected row ends before its item, so the tree
        # takes a style that leaves that band to the delegate's tint
        self.directory_tree.setStyle(
            _DirectorySelectionStyle(
                QStyleFactory.create(QApplication.style().objectName())
            )
        )
        self.path_label.setContentsMargins(
            self.directory_tree.header_text_indent(), 0, 0, 0
        )
        self.tabs = QTabWidget()
        # the state filter button is not a corner widget any more: it is placed
        # over the State column of the active tab's header, aligned to the right
        # of that column. It keeps a fixed parent so a closed tab cannot destroy
        # it; it is only repositioned over whichever header is current.
        self._state_filter: str | None = None
        self.state_filter_button = _icon_button(
            self.tabs, "Filter by state", _draw_filter, "StateFilter"
        )
        # the directory header icons are small; match them so the filter button
        # reads as part of the same icon set rather than standing out larger
        self.state_filter_button.setIconSize(
            QSize(_HEADER_ICON_SIZE, _HEADER_ICON_SIZE)
        )
        self.state_filter_button.setCheckable(True)
        self.state_filter_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.state_filter_menu = QMenu(self.state_filter_button)
        group = QActionGroup(self.state_filter_menu)
        for offered in (None, *_OFFERED_STATES):
            action = QAction(offered or "All states", group)
            action.setCheckable(True)
            action.setChecked(offered is None)
            action.triggered.connect(
                lambda _checked=False, chosen=offered: self.set_state_filter(chosen)
            )
            self.state_filter_menu.addAction(action)
        self.state_filter_button.clicked.connect(self._open_state_filter_menu)
        # the header of the active tab the button is currently positioned over;
        # None while no tab holds a State column
        self._state_filter_header = None
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.preview_area = PreviewPanel()
        # the table over the preview, resizable between them, the table taking
        # the larger share
        self.table_splitter = QSplitter(Qt.Orientation.Vertical)
        self.table_splitter.addWidget(self.tabs)
        self.table_splitter.addWidget(self.preview_area)
        self.table_splitter.setStretchFactor(0, 3)
        self.table_splitter.setStretchFactor(1, 2)
        self.rail = QWidget()
        self.choose_button = _icon_button(
            self.directory_tree.header_view, "Choose...", _draw_choose, "Choose"
        )
        self.up_button = _icon_button(
            self.directory_tree.header_view, "Up", _draw_up, "Up"
        )
        self.refresh_button = _icon_button(
            self.rail, "Refresh", _draw_refresh, "Refresh"
        )
        # the rail is as wide as the buttons it carries, and the toggle bar
        # fills the rest of its height below Refresh
        self.rail_width = self.refresh_button.sizeHint().width() + 2 * _RAIL_PADDING
        self.rail.setFixedWidth(self.rail_width)
        self.toggle_button = PaneToggle(self.rail)
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.setFixedWidth(self.rail_width)
        self.toggle_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        self.toggle_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setToolTip("Hide panel")
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Task title")
        self.target_label = QLabel()
        # the hint goes where the task is created, in the font it already uses,
        # so it adds no height of its own and only the colour tells it apart
        self.target_label.setWordWrap(False)
        # no colour is written down: the hint reads the palette, so it follows a
        # light or dark mode like the rest of the interface
        self.target_label.hide()
        self.create_button = QPushButton("Create")

        self.directory_tree.set_navigation_buttons(self.choose_button, self.up_button)

        self.path_row = QWidget()
        path_layout = QHBoxLayout(self.path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.path_label, 1)

        self.search_panel = SearchPanel(_MARGIN)

        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        # the panes meet at the splitter, so the inner edges carry no margin and
        # the gap between them is the handle alone
        left_layout.setContentsMargins(_MARGIN, _MARGIN, 0, _MARGIN)
        left_layout.setSpacing(0)
        left_layout.addWidget(self.directory_tree.header_view)
        left_layout.addWidget(self.path_row)
        # the tree and the reminders panel take turns under the shared header,
        # which stays outside the stack; the tree is only hidden, never rebuilt,
        # so its selection and the creation target survive a swap
        self.directory_stack = QStackedLayout()
        self.directory_stack.setContentsMargins(0, 0, 0, 0)
        self.directory_stack.setSpacing(0)
        left_layout.addLayout(self.directory_stack)
        self.directory_stack.addWidget(self.directory_tree)

        self.directory_panel = self.left_panel

        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.addWidget(self.left_panel)
        self.left_splitter.addWidget(self.search_panel)
        self.left_splitter.setStretchFactor(0, 3)
        self.left_splitter.setStretchFactor(1, 2)
        self.left_panel.setMinimumHeight(80)
        self.search_panel.setMinimumHeight(60)

        self.left_container = QWidget()
        left_container_layout = QVBoxLayout(self.left_container)
        left_container_layout.setContentsMargins(0, 0, 0, 0)
        left_container_layout.setSpacing(0)
        left_container_layout.addWidget(self.left_splitter)

        self.bottom_bar = QWidget()
        self.clear_target_button = _icon_button(
            self.bottom_bar, "Clear destination", _draw_cross, "ClearTarget"
        )
        self.clear_target_button.setIconSize(QSize(_SMALL_ICON_SIZE, _SMALL_ICON_SIZE))
        self.clear_target_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_target_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_target_button.hide()
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self.title_input, 1)
        bottom_layout.addWidget(self.target_label)
        # the clear button rides with the label at the top of the row, so it
        # takes no height from the bar
        bottom_layout.addWidget(self.clear_target_button, 0, Qt.AlignmentFlag.AlignTop)
        bottom_layout.addWidget(self.create_button)

        # the rail carries Refresh at its top and, below it, the pane toggle;
        # it spans the full height of the right pane, to the left of everything
        # else the pane holds
        rail_layout = QVBoxLayout(self.rail)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setSpacing(0)
        rail_layout.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignHCenter)
        rail_layout.addWidget(self.toggle_button, 1)

        # the rail spans the full height of the pane, so it takes the first
        # column of a grid while the bar and the table share the second; the
        # table and the preview below it share that cell through a splitter
        self.right_panel = QWidget()
        right_layout = QGridLayout(self.right_panel)
        right_layout.setContentsMargins(0, _MARGIN, _MARGIN, _MARGIN)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.rail, 0, 0, 2, 1)
        right_layout.addWidget(self.bottom_bar, 0, 1)
        right_layout.addWidget(self.table_splitter, 1, 1)
        right_layout.setColumnStretch(1, 1)
        right_layout.setRowStretch(1, 1)

        self.splitter = QSplitter()
        self.splitter.addWidget(self.left_container)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(1, 2)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        self.title_bar = TitleBar(self)
        container_layout.addWidget(self.title_bar)
        container_layout.addWidget(self.splitter, 1)
        self.setCentralWidget(container)
        self.resize_grips = ResizeGrips(self, container)

        self.choose_button.clicked.connect(self.choose_directory)
        self.up_button.clicked.connect(self.go_up)
        self.refresh_button.clicked.connect(self.refresh)
        # clearing the selection is what hides the label and the button: it
        # fires itemSelectionChanged, the same signal any tree click fires
        self.clear_target_button.clicked.connect(self.directory_tree.clear_subdirectory)
        self.directory_tree.itemDoubleClicked.connect(self.open_directory)
        self.directory_tree.itemSelectionChanged.connect(self._sync_creation_target)
        self.directory_tree.category_requested.connect(self.new_category)
        self.directory_tree.bell_button.toggled.connect(self._toggle_reminders)
        self.title_input.returnPressed.connect(self.create_task)
        self.create_button.clicked.connect(self.create_task)
        self.search_panel.task_activated.connect(self._select_task)
        self.toggle_button.clicked.connect(self.toggle_left_pane)
        # Ctrl+N starts a new task and Ctrl+F searches, wherever the focus is
        self.new_task_shortcut = QShortcut(QKeySequence.StandardKey.New, self)
        self.new_task_shortcut.activated.connect(self.title_input.setFocus)
        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self._focus_search)
        self.splitter.splitterMoved.connect(self._update_path_label)
        self.splitter.splitterMoved.connect(self._update_toggle_tooltip)
        # the preview follows the selection of the current tab, so a new tab
        # or a rebuilt one hides it until a task of it is selected
        self.tabs.currentChanged.connect(self._sync_preview)

        # the old bar's focus order, kept by hand because the panels now hold
        # the same widgets in a different tree; the search panel sits between
        # the tree and the table, where it lives in the pane
        self.setTabOrder(self.choose_button, self.up_button)
        self.setTabOrder(self.up_button, self.refresh_button)
        self.setTabOrder(self.refresh_button, self.directory_tree)
        self.setTabOrder(self.directory_tree, self.search_panel.search_input)
        self.setTabOrder(
            self.search_panel.search_input, self.search_panel.search_results
        )
        self.setTabOrder(self.search_panel.search_results, self.tabs)
        self.setTabOrder(self.tabs, self.title_input)
        self.setTabOrder(self.title_input, self.create_button)

    def set_state_filter(self, wanted: str | None) -> None:
        """Shows only the tasks in a state, in every tab but `Closed`.

        Args:
            wanted: the state to show, or None for every state.
        """
        self._state_filter = wanted
        self.state_filter_button.setChecked(wanted is not None)
        self.state_filter_button.setToolTip(
            f"Filter by state: {wanted}" if wanted else "Filter by state"
        )
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) != _CLOSED_TAB:
                cast(TaskPanel, self.tabs.widget(index)).listing.set_state_filter(
                    wanted
                )

    def _open_state_filter_menu(self) -> None:
        """Opens the state menu under the filter button.

        A click toggles a checkable button, so its check is put back to what
        the filter says before the menu opens.
        """
        self.state_filter_button.setChecked(self._state_filter is not None)
        button = self.state_filter_button
        self.state_filter_menu.popup(button.mapToGlobal(button.rect().bottomLeft()))

    def _place_state_filter_button(self, _index: int | None = None) -> None:
        """Places the state filter button over the State column of the active tab.

        The button keeps a fixed parent, so closing a tab never destroys it; it
        is only repositioned over the header of whichever tab is current, aligned
        to the right edge of the State column. It is hidden when no tab is active
        or when the State column has no room for it.

        The header's resize slot must already be connected before this runs;
        connection is handled by `_connect_state_filter_header` at header
        assignment time, never here, so a column resize cannot accumulate
        duplicate connections.
        """
        # a menu opened over a tab that is about to change must be closed first,
        # otherwise it keeps pointing at the old button position
        self.state_filter_menu.hide()

        button = self.state_filter_button
        panel = self.tabs.currentWidget()
        if panel is None:
            button.hide()
            return

        header = cast(TaskPanel, panel).listing.header

        state_size = header.sectionSize(STATE_COLUMN)
        if state_size <= 0:
            button.hide()
            return

        # keep the button from covering the resize handle between State and the
        # next column
        bhint = button.sizeHint()
        available = state_size - _STATE_FILTER_MARGIN
        if available < bhint.width():
            button.hide()
            return

        x = (
            header.sectionPosition(STATE_COLUMN)
            + state_size
            - bhint.width()
            - _STATE_FILTER_MARGIN
        )
        y = (header.height() - bhint.height()) // 2
        pt = self.tabs.mapFromGlobal(header.mapToGlobal(QPoint(x, y)))
        button.move(pt.x(), pt.y())
        button.resize(bhint.width(), bhint.height())
        button.show()

    def _connect_state_filter_header(self, header) -> None:
        """Connects the resize slot to the header of the active tab, once.

        Runs exactly once per header at header assignment time. The previous
        header is disconnected only when the header actually changes, so a slot
        never points at a header destroyed by a tab rebuild. `Qt.UniqueConnection`
        guards against any duplicate connection regressions.
        """
        old = self._state_filter_header
        if old is not None and old is not header:
            try:
                old.sectionResized.disconnect(self._on_state_section_resized)
            except TypeError:
                pass
        if header is not None and header is not self._state_filter_header:
            self._state_filter_header = header
            header.sectionResized.connect(
                self._on_state_section_resized, type=Qt.ConnectionType.UniqueConnection
            )

    def _on_state_section_resized(self, _logical: int, _old: int, _new: int) -> None:
        """Replaces the filter button when the State column of the active tab
        is resized, and keeps the column above its minimum width so the state
        text never overlaps the funnel filter button."""
        header = self._state_filter_header
        if header is not None and _logical == STATE_COLUMN:
            minimum = _state_column_min_width()
            if _new < minimum:
                # dragging the separator below the floor would make the state
                # text overlap the button; push it back to the minimum.
                header.resizeSection(STATE_COLUMN, minimum)
                return
        self._place_state_filter_button()

    def _on_tab_changed(self, _index: int) -> None:
        """Connects the new active tab's header exactly once, then positions
        the filter button over its State column."""
        panel = self.tabs.currentWidget()
        if panel is not None:
            self._connect_state_filter_header(cast(TaskPanel, panel).listing.header)
        self._place_state_filter_button(_index)

    def _focus_search(self) -> None:
        """Puts the focus in the search field, with its text selected."""
        self.search_panel.search_input.setFocus()
        self.search_panel.search_input.selectAll()

    def _splitters(self) -> dict[str, QSplitter]:
        """Returns every splitter of the window under the key it is saved with."""
        return {
            "window/main_splitter": self.splitter,
            "window/directory_splitter": self.left_splitter,
            "window/table_splitter": self.table_splitter,
            "window/preview_splitter": self.preview_area,
        }

    def _restore_state(self) -> None:
        """Restores the size of the window and of every splitter, when saved.

        A value that is missing or does not read back is ignored silently, so
        the window opens with the defaults it has always opened with.
        """
        geometry = self.settings.value(_GEOMETRY_KEY)
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)

        for key, splitter in self._splitters().items():
            state = self.settings.value(key)
            if isinstance(state, QByteArray):
                splitter.restoreState(state)

    def _save_state(self) -> None:
        """Saves the size of the window and of every splitter for the next run."""
        self.settings.setValue(_GEOMETRY_KEY, self.saveGeometry())

        for key, splitter in self._splitters().items():
            self.settings.setValue(key, splitter.saveState())

    def attach_reminder_scheduler(self, scheduler: ReminderScheduler) -> None:
        """Takes the scheduler and adds the reminders panel behind the bell.

        Without a scheduler there is no panel and the bell stays hidden.

        Args:
            scheduler: the scheduler the reminders are read from and removed
                through.
        """
        self.reminder_scheduler = scheduler
        self.reminders_list = RemindersList(
            scheduler, resolver=self._resolve_reminder_task
        )
        self.reminders_panel = QWidget()
        panel_layout = QVBoxLayout(self.reminders_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)
        panel_layout.addWidget(self.reminders_list)
        self.directory_stack.addWidget(self.reminders_panel)
        # the panel is read again whenever it comes on show, so a reminder
        # added while the tree stood there is there when the bell is clicked
        self.directory_stack.currentChanged.connect(self._refresh_reminders_panel)
        self.reminders_list.task_clicked.connect(self._select_reminder_task)
        self.directory_tree.show_bell()

    def _toggle_reminders(self, checked: bool) -> None:
        """Swaps the left panel between the directory tree and the reminders.

        Only the header title and buttons change; the tree keeps its selection.

        Args:
            checked: whether the reminders panel takes the place of the tree.
        """
        page = self.reminders_panel if checked else self.directory_tree
        if page is None:
            return

        for button in (
            self.choose_button,
            self.up_button,
            self.directory_tree.header_button,
        ):
            button.setVisible(not checked)
        self.directory_tree.set_header_label(
            _REMINDERS_HEADER if checked else _DIRECTORY_HEADER
        )
        self.directory_stack.setCurrentWidget(page)

    def _refresh_reminders_panel(self, index: int) -> None:
        """Reads the reminders again whenever the stack shows their panel."""
        if (
            self.reminders_panel is not None
            and self.reminders_list is not None
            and index == self.directory_stack.indexOf(self.reminders_panel)
        ):
            self.reminders_list.refresh()

    def _resolve_reminder_task(self, task: str) -> Path | None:
        """Finds the task a reminder names among the entries of the last reload.

        The name is the folder name, or the archive stem for a closed task. With
        duplicates the first wins.

        Args:
            task: the task folder name the reminder carries.

        Returns:
            The `.md` of the task or the archive that holds it, or None when no
            entry of the reload carries the name.
        """
        for entry, _ in self.search_panel.entries:
            name = (
                entry.file.stem
                if standards.is_task_archive(entry.file.name)
                else entry.file.parent.name
            )
            if name == task:
                return entry.file
        return None

    def _select_reminder_task(self, task: str) -> None:
        """Selects the task a reminder names, the way a search result does.

        Args:
            task: the task folder name the reminder carries.
        """
        path = self._resolve_reminder_task(task)
        if path is not None:
            self._select_task(path)

    def _align_header(self) -> None:
        """Gives every panel title the height of the tab bar, so they read as one
        set.
        """
        height = self.tabs.tabBar().sizeHint().height()
        self.directory_tree.header_view.setFixedHeight(height)
        self.search_panel.search_header.setFixedHeight(height)
        self.preview_area.preview_text_header.setFixedHeight(height)
        self.preview_area.preview_list_header.setFixedHeight(height)

    def _update_path_label(self) -> None:
        """Shows the current directory, elided to the room the row has."""
        path = str(self.current_directory)
        metrics = self.path_label.fontMetrics()
        margins = self.path_label.contentsMargins()
        room = self.path_label.width() - margins.left() - margins.right()
        self.path_label.setText(
            metrics.elidedText(path, Qt.TextElideMode.ElideMiddle, room)
        )
        self.path_label.setToolTip(path)

    def toggle_left_pane(self) -> None:
        """Collapses the left pane, or restores its previous width.

        Falls back to the initial split, then to a third of the window, when no
        width was remembered.
        """
        sizes = self.splitter.sizes()
        total = sum(sizes)

        if sizes[0] > 0:
            self._left_width = sizes[0]
            self.splitter.setSizes([0, total])
        else:
            width = self._left_width or self._initial_left_width
            if not width:
                # No valid previous width (e.g. after restart with collapsed panel):
                # use a sensible default (1/3 of total, matching the 1:2 stretch ratio)
                width = max(total // 3, 1)
            # Clamp so the right panel keeps a non-zero width
            width = min(width, max(total - 1, 1))
            self.splitter.setSizes([width, total - width])

        self._update_toggle_tooltip()

    def _update_toggle_tooltip(self) -> None:
        """Words and points the toggle bar at what the next click will do."""
        collapsed = self.splitter.sizes()[0] == 0
        self.toggle_button.setToolTip("Show panel" if collapsed else "Hide panel")
        self.toggle_button.set_points_right(collapsed)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_path_label()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # the frameless window keeps no native frame, so on Windows the
        # thick-frame, caption, minimize and maximize styles needed for
        # Aero Snap are applied once, after the first show; the helper is
        # inert on other platforms
        if not self._snap_styles_applied:
            enable_snap_styles(int(self.winId()))
            self._snap_styles_applied = True
        if self._initial_left_width is None:
            self._initial_left_width = self.splitter.sizes()[0]
        self._align_header()
        self._update_path_label()
        self._update_toggle_tooltip()
        # the button is positioned over the State column of the active tab's
        # header; that only works once the window has been shown and the
        # header holds real screen coordinates, so place it here rather than
        # during construction (when mapToGlobal would still return zeros)
        panel = self.tabs.currentWidget()
        if panel is not None:
            self._connect_state_filter_header(cast(TaskPanel, panel).listing.header)
        self._place_state_filter_button()

    def nativeEvent(
        self,
        event_type: QByteArray | bytes | bytearray | memoryview,
        message: int,
        /,
    ) -> object:
        result = handle_native_event(bytes(cast(bytes, event_type)), int(message))
        if result is not None:
            return result
        return super().nativeEvent(event_type, message)

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
            self.clear_target_button.hide()
            self.tabs.clear()
            # the listings hold nothing, so the search panel holds nothing
            self._reload_search([])
            return

        self._reload_tree()
        # the listings are built again on every reload, so they are told the
        # destination the tree holds once they exist
        self._reload_tasks()
        self._sync_creation_target()

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
        """Returns the directory a new task is created in: the selected category,
        or the current directory.

        Returns:
            The directory to create the task in.
        """
        return self._selected_directory() or self.current_directory

    def select_destination(self, category: str) -> None:
        """Makes a category the creation target, as clicking it in the tree would.

        The heading of the base folder clears the selection instead.

        Args:
            category: the path the heading carries.
        """
        path = Path(category)
        if path == self.current_directory:
            self.directory_tree.clear_subdirectory()
            return

        self.directory_tree.select_subdirectory(path)

    def _sync_creation_target(self) -> None:
        """Points the target line at the directory a new task would land in."""
        target = self.creation_directory()
        selected = self._selected_directory()

        # the marker that stands for the destination is carried by the listings
        # themselves, so every one of them follows the selection
        for index in range(self.tabs.count()):
            panel = cast(TaskPanel, self.tabs.widget(index))
            panel.listing.set_destination(selected)

        if target == self.current_directory:
            self.target_label.hide()
            self.clear_target_button.hide()
            return

        # the path label beside it already names the base directory, so the name
        # of the category says it all and the full path stays in the tooltip
        self.target_label.setText(f"New tasks in {target.name}")
        self.target_label.setToolTip(str(target))
        self.target_label.show()
        # the clear button is part of the line: it shows and hides with it
        self.clear_target_button.show()

    def _sync_preview(self) -> None:
        """Shows the task selected in the current tab, or hides the preview."""
        panel = self.tabs.currentWidget()
        entry = (
            cast(TaskPanel, panel).listing.selected_entry()
            if panel is not None
            else None
        )
        self.preview_area.show_entry(entry)

    def _reload_tasks(self) -> None:
        # one day for the whole listing, so a refresh that runs as the date turns
        # does not date half of the tasks to yesterday
        today = datetime.datetime.now().astimezone().date()
        sections = self._sections()
        active = (
            self.tabs.tabText(self.tabs.currentIndex()) if self.tabs.count() else ""
        )

        self.tabs.clear()

        every = self._new_listing(_ALL_TAB)
        shut = self._new_listing(_CLOSED_TAB)
        closed_here = False
        dividers: list[tuple[str, Path | None]] = []

        for title, group in sections:
            standing = [entry for entry in group.entries if entry.state != "closed"]
            archived = [entry for entry in group.entries if entry.state == "closed"]

            if standing:
                # the heading of the base folder carries the directory itself,
                # so a click on it clears the destination instead of picking one
                self._add_heading(
                    every, title, group.category or self.current_directory
                )
                for entry in standing:
                    self._add_task(every, entry, today)
            elif group.divider:
                # a category that holds no task that stands stands as a heading
                # of its own, so a task can be dropped on it and a new one can
                # land there; it carries no task to order by, so it goes last
                # among the headings
                dividers.append((title, group.category))

            if archived:
                self._add_heading(shut, title)
                for entry in archived:
                    self._add_task(shut, entry, today)
                closed_here = True

        for title, category in dividers:
            self._add_heading(every, title, category)

        self._add_tab(_ALL_TAB, every)

        for title, group in sections:
            standing = [entry for entry in group.entries if entry.state != "closed"]
            if not standing:
                continue

            tab = self._new_listing(title, group.category or self.current_directory)
            for entry in standing:
                self._add_task(tab, entry, today)
            self._add_tab(title, tab)

        if closed_here:
            self._add_tab(_CLOSED_TAB, shut)

        self._select_tab(active)
        panel = self.tabs.currentWidget()
        if panel is not None:
            self._connect_state_filter_header(cast(TaskPanel, panel).listing.header)
        self._place_state_filter_button()
        self._reload_search([
            (entry, title) for title, group in sections for entry in group.entries
        ])

    def _reload_search(self, entries: list[tuple[listing.TaskEntry, str]]) -> None:
        """Points the search panel at the tasks of a reload."""
        self.search_panel.set_entries(
            entries, self.current_directory, self._base_title()
        )

    def _select_task(self, path: Path) -> None:
        """Selects a task in whichever tab holds it, leaving the destination as it
        is.

        Args:
            path: the .md of the task, or the archive that holds it.
        """
        panel = cast(TaskPanel, self.tabs.currentWidget())
        if panel is None:
            return

        panel.listing.select_task(path)

    def _sections(self) -> list[tuple[str, listing.TaskGroup]]:
        """Pairs every task group with its tab title.

        Empty categories are included so they still show as headings.

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

    def _new_listing(self, title: str, category: Path | None = None) -> TaskListing:
        tab = TaskListing()
        tab.set_category(category)
        tab.open_requested.connect(self.open_task)
        tab.resume_requested.connect(self.resume_task)
        tab.rename_requested.connect(self.rename_task)
        tab.state_requested.connect(self.change_state)
        tab.close_requested.connect(self.close_task)
        tab.move_requested.connect(self.move_task)
        tab.order_changed.connect(
            lambda column, descending, name=title: self._remember_sort(
                name, column, descending
            )
        )
        tab.destination_requested.connect(self.select_destination)
        # the preview follows the selection through the same path the action
        # bar takes, so nothing of it needs a special case for `Esc` or a click
        # on a category heading
        tab.itemSelectionChanged.connect(self._sync_preview)
        # escape in the table drops the task and, with it, the destination: it
        # clears the tree through the same handler the label's 'x' calls
        tab.escape_shortcut.activated.connect(self.directory_tree.clear_subdirectory)
        return tab

    def _remember_sort(self, title: str, column: int, descending: bool) -> None:
        """Keeps the column and the direction a tab was last sorted by."""
        self._sorts[title] = (column, descending)

    def _add_tab(self, title: str, tab: TaskListing) -> None:
        if title in self._sorts:
            tab.set_sort(*self._sorts[title])
        if title != _CLOSED_TAB:
            tab.set_state_filter(self._state_filter)
        tab.fit_task_column()
        self.tabs.addTab(TaskPanel(tab), title)

    def _select_tab(self, title: str) -> None:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.tabs.setCurrentIndex(index)
                return

        self.tabs.setCurrentIndex(0)

    def _add_heading(
        self, tab: QListWidget, text: str, category: Path | None = None
    ) -> None:
        item = QListWidgetItem(text)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        # only a heading that stands for a live category is worth storing: an
        # archive heading names no folder a new task could land in, so clicking
        # one cannot pick a destination
        if category is not None:
            item.setData(_CATEGORY_ROLE, str(category))
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
        if standards.is_task_archive(entry.file.name):
            # a closed task stands as an archive, which is not a folder to
            # move, so its row is not dragged anywhere
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
        tab.addItem(item)

    def choose_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose directory", str(self.current_directory)
        )
        if selected:
            folder = Path(selected)
            # the shared config file is where the base folder lives now, so
            # the CLI works in the same folder from its next run
            config.save_config(folder)
            self.navigate_to(folder)

    def go_up(self) -> None:
        parent = self.current_directory.parent
        if parent != self.current_directory:
            self.navigate_to(parent)

    def open_directory(self, item: QTreeWidgetItem, _column: int) -> None:
        path = item.data(0, _PATH_ROLE)
        if path:
            self.navigate_to(Path(path))

    def new_category(self) -> None:
        """Asks for a name and creates a category in the current directory.

        The category is selected afterwards, new or existing, so the next task
        lands in it.
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
        """Adds a dated section to a task and opens it, reopening it first when it
        is archived.

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
        """Sets the state of a task by hand. Nothing is opened.

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
        """Archives a task into a verified zip. Nothing is opened.

        Args:
            entry: the selected task.
        """
        try:
            tasks.close_task(entry.file.parent, entry.title)
        except tasks.TaskInUseError:
            QMessageBox.warning(
                self,
                "mktsk",
                "Could not close the task: some of its files are in use. "
                "Close them and try again.",
            )
            return
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.refresh()

    def move_task(self, folder: Path, category: Path) -> None:
        """Moves a task folder into a category and keeps it selected.

        A title clash or an I/O error is shown in a message box and leaves the
        list as it was.

        Args:
            folder: the folder of the task to move.
            category: the category the task is to stand in.
        """
        try:
            moved = tasks.move_task(folder, category)
        except (OSError, helpers.TaskError) as error:
            QMessageBox.critical(self, "mktsk", str(error))
            return

        self.refresh()
        title = standards.task_folder_title(moved.name) or moved.name
        self._select_task(moved / f"{title}.md")

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

    def _drop_entry(self) -> listing.TaskEntry | None:
        """Returns the selected task when files can be dropped into it.

        A closed task is an archive and takes nothing.

        Returns:
            The selected task, or None when no task is selected or the
            selected one is closed.
        """
        panel = self.tabs.currentWidget()
        if panel is None:
            return None

        entry = cast(TaskPanel, panel).listing.selected_entry()
        if entry is None or entry.state == "closed":
            return None

        return entry

    def _drop_paths(self, mime: QMimeData) -> list[Path]:
        """Returns the local files a drag carries; other URLs are ignored.

        Args:
            mime: the payload of the drag.

        Returns:
            The paths of the local files the drag carries.
        """
        if not mime.hasUrls():
            return []

        return [Path(url.toLocalFile()) for url in mime.urls() if url.toLocalFile()]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accepts a drag of files when an open task is selected.

        Other drags are left to the widget they belong to.

        Args:
            event: the drag that entered.
        """
        if self._drop_entry() is None or not self._drop_paths(event.mimeData()):
            event.ignore()
            return

        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        """Moves the dropped files into the selected task and keeps it selected.

        Args:
            event: the drop.
        """
        entry = self._drop_entry()
        paths = self._drop_paths(event.mimeData())

        if entry is None or not paths:
            event.ignore()
            return

        event.accept()

        result = files.move_into_task(paths, entry.file.parent)

        self.refresh()
        self._select_task(entry.file)

        if result.skipped:
            self._warn_skipped(result.skipped)

    def _warn_skipped(self, skipped: list[tuple[Path, str]]) -> None:
        """Warns about the files a drop did not move.

        Args:
            skipped: each file that was not moved, with the reason why.
        """
        QMessageBox.warning(self, "mktsk", _skipped_message(skipped))

    def quit_application(self) -> None:
        """Requests a real quit: saves the layout and quits the application.

        Sets the quit flag so a close event that follows is accepted rather
        than hiding the window to the tray.
        """
        self._quitting = True
        self._save_state()
        if self._instance_lock is not None:
            self._instance_lock.unlock()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        # with a tray active and no real quit in progress, closing hides the
        # window to the tray instead of quitting; a session save always quits
        app = QGuiApplication.instance()
        saving = isinstance(app, QGuiApplication) and app.isSavingSession()
        if self.tray_controller is not None and not self._quitting and not saving:
            self._save_state()
            self.hide()
            event.ignore()
            return
        self._save_state()
        super().closeEvent(event)
