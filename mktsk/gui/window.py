"""The main window, over the task logic the CLI uses."""

import datetime
from pathlib import Path
from typing import cast

from PySide6.QtCore import (
    QByteArray,
    QMimeData,
    QPointF,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QUrl,
)
from PySide6.QtGui import (
    QBrush,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QResizeEvent,
    QShortcut,
    QShowEvent,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyleFactory,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mktsk import config, files, helpers, listing, standards, state, tasks

from .app_icon import app_icon, set_app_identity
from .icons import (
    _CHEVRON_HALF_HEIGHT,
    _SMALL_ICON_SIZE,
    _draw_chevron,
    _draw_choose,
    _draw_cross,
    _draw_refresh,
    _draw_up,
    _icon_button,
)
from .tasklist import (
    _AGE_ROLE,
    _CATEGORY_ROLE,
    _COUNT_ROLE,
    _ENTRY_ROLE,
    _STATE_ROLE,
    TaskListing,
    TaskPanel,
    _date_cell,
    _DirectorySelectionStyle,
    _relative_age,
    _UnifiedSelectionDelegate,
)
from .tree import _PATH_ROLE, _CategoryTree

_ALL_TAB = "All"
_CLOSED_TAB = "Closed"

# the title of the left Directory header, kept in one place so the tree can hide
# it when the header is too narrow to hold it before the buttons
_DIRECTORY_HEADER = "Directory"

# the outer margin the left Directory header, the tab bar and the bottom bar
# share, so the two panes line up on a single grid
_MARGIN = 6

# the side rail is as wide as the Refresh button it carries plus this padding,
# so its width follows the style rather than a pixel figure of its own
_RAIL_PADDING = 2

# the separator line of the toggle bar: how far it stops short of the ends of
# the bar, and of the chevron it is interrupted by, in logical pixels
_TOGGLE_LINE_MARGIN = 6.0
_TOGGLE_LINE_GAP = 4.0

# how many files a drop that left some out names in the warning about it; the
# rest are counted in a line of their own, so a long list never fills it
_MAX_SKIPPED_NAMED = 10

# the key the window keeps its size and position under; the splitters keep
# theirs under the keys `_splitters` gives them
_GEOMETRY_KEY = "window/geometry"


def _task_text(file: Path) -> str:
    """Reads the raw text of a task .md for the preview.

    The text is shown as it stands, with no Markdown rendering, and a file
    that cannot be read previews as empty rather than raising: one unreadable
    file never brings the listing down, and it does not bring the preview down
    either. A byte that is not valid utf-8 is replaced rather than failing the
    read, so a file with one still shows everything around it.

    Args:
        file: the .md of the task.

    Returns:
        The text of the file, or nothing when it cannot be read.
    """
    try:
        return file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _panel_title(text: str) -> QHeaderView:
    """Builds the title of one panel of the preview.

    The `Directory` and `Search` headers are standalone `QHeaderView`s over a
    model that carries their title, so a panel title is built the same way: a
    one-section model holding just the title gives the header the native
    header look, its font and its colours from the palette, with nothing
    written down. The header takes no click, no sort and no focus, so a title
    is only ever read.

    Args:
        text: the title of the panel.

    Returns:
        The header showing the title, ready to sit above the panel content.
    """
    model = QStandardItemModel()
    model.setColumnCount(1)
    model.setHorizontalHeaderLabels([text])
    header = QHeaderView(Qt.Orientation.Horizontal)
    header.setModel(model)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    return header


def _set_panel_title(header: QHeaderView, text: str) -> None:
    """Replaces the title a panel header carries.

    Args:
        header: the header built by `_panel_title`.
        text: the title to show.
    """
    model = header.model()

    if model is not None:
        model.setHeaderData(0, Qt.Orientation.Horizontal, text)


def _skipped_message(skipped: list[tuple[Path, str]]) -> str:
    """Builds the text of the warning about the files a drop did not move.

    At most ten of them are named, each with the reason it was left out, and
    the rest are counted in a line of their own, so a long list never fills
    the warning.

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


class _PaneToggle(QToolButton):
    """The pane toggle, drawn as a line down its centre broken by a chevron.

    The direction of the chevron is handed in by the window, from the same
    state that words the tooltip, so the bar paints what it is told.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._points_right = False

    def set_points_right(self, points_right: bool) -> None:
        """Turns the chevron to the side the next click opens, and repaints.

        Args:
            points_right: True for a chevron pointing right.
        """
        self._points_right = points_right
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        chevron_colour = palette.color(QPalette.ColorRole.ButtonText)
        idle = palette.color(QPalette.ColorRole.Mid)
        line_colour = chevron_colour if self.underMouse() else idle
        centre = self.rect().center()
        x = centre.x()
        painter.setPen(QPen(line_colour, 1))
        painter.drawLine(
            QPointF(x, _TOGGLE_LINE_MARGIN),
            QPointF(x, centre.y() - _CHEVRON_HALF_HEIGHT - _TOGGLE_LINE_GAP),
        )
        painter.drawLine(
            QPointF(x, centre.y() + _CHEVRON_HALF_HEIGHT + _TOGGLE_LINE_GAP),
            QPointF(x, self.height() - _TOGGLE_LINE_MARGIN),
        )
        _draw_chevron(painter, QRectF(self.rect()), self._points_right, chevron_colour)
        painter.end()


class MainWindow(QMainWindow):
    """Desktop interface over the CLI task logic."""

    def __init__(
        self, settings: QSettings | None = None, base_folder: Path | None = None
    ) -> None:
        super().__init__()
        self.settings = settings or QSettings("mktsk", "mktsk")
        self._sorts: dict[str, tuple[int, bool]] = {}
        # the tasks the search panel filters over, each with the title of its
        # category, kept until the next reload hands in new ones
        self._search_entries: list[tuple[listing.TaskEntry, str]] = []
        # the width the left pane had before the toggle bar collapsed it, and
        # the split the splitter opened with, to fall back on when a collapse
        # came from dragging the handle rather than from the bar
        self._left_width: int | None = None
        self._initial_left_width: int | None = None
        # whether the attachment list of the preview stands for a closed task,
        # whose entries open the archive itself rather than a folder on disk
        self._archived_preview = False
        # the folder the first-run flow resolved lives in the shared config
        # file, so it is handed in rather than read from QSettings
        self.current_directory = base_folder or Path.cwd()
        self.setWindowTitle("mktsk")
        # the window carries the icon the application draws for itself
        self.setWindowIcon(app_icon())
        # the taskbar shows the application by the identity it sets here
        set_app_identity()
        self.setMinimumSize(640, 420)
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
        # the preview of the selected task: the raw text of the .md beside the
        # names of the other attachments, both read-only and neither in the
        # tab order, so the tabs keep the order they had
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.preview_list = QListWidget()
        self.preview_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.preview_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.preview_list.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.preview_list.setAlternatingRowColors(True)
        self.preview_list.setItemDelegate(_UnifiedSelectionDelegate(self.preview_list))
        self.preview_list.itemDoubleClicked.connect(self._open_attachment)
        self.preview_list.keyPressEvent = self._preview_list_key_press
        # each panel opens with its title over the content, carried by the
        # same standalone header as `Directory` and `Search`, so it reads as
        # one set with them and adds nothing of its own
        self.preview_text_header = _panel_title("Details")
        self.preview_list_header = _panel_title("Attachments")
        self.preview_text_panel = QWidget()
        text_layout = QVBoxLayout(self.preview_text_panel)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        text_layout.addWidget(self.preview_text_header)
        text_layout.addWidget(self.preview_text, 1)
        self.preview_list_panel = QWidget()
        list_layout = QVBoxLayout(self.preview_list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)
        list_layout.addWidget(self.preview_list_header)
        list_layout.addWidget(self.preview_list, 1)
        self.preview_area = QSplitter(Qt.Orientation.Horizontal)
        self.preview_area.addWidget(self.preview_text_panel)
        self.preview_area.addWidget(self.preview_list_panel)
        self.preview_area.setStretchFactor(0, 3)
        self.preview_area.setStretchFactor(1, 1)
        # hidden until a task is selected, so the table keeps the full height
        self.preview_area.hide()
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
        self.toggle_button = _PaneToggle(self.rail)
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
        hint = self.target_label.palette()
        hint.setColor(
            QPalette.ColorRole.WindowText,
            hint.color(QPalette.ColorRole.PlaceholderText),
        )
        self.target_label.setPalette(hint)
        self.target_label.hide()
        self.create_button = QPushButton("Create")

        # the search panel under the tree: its header shares the single model
        # of the results, so it carries the `Search` title the way the tree's
        # own header carries `Directory`, with the other two sections hidden
        self.search_results = QTreeWidget()
        self.search_results.setColumnCount(3)
        self.search_results.setHeaderLabels(["Search", "", ""])
        self.search_results.setHeaderHidden(True)
        self.search_results.setRootIsDecorated(False)
        self.search_results.setFrameShape(QFrame.Shape.NoFrame)
        results_header = self.search_results.header()
        results_header.setStretchLastSection(False)
        results_header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        results_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        results_header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed
        )
        self.search_results.setColumnWidth(2, 65)
        self.search_header = QHeaderView(Qt.Orientation.Horizontal)
        self.search_header.setModel(self.search_results.model())
        self.search_header.setSectionHidden(1, True)
        self.search_header.setSectionHidden(2, True)
        self.search_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.search_header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search tasks")
        self.search_input.setClearButtonEnabled(True)

        self.directory_tree.set_navigation_buttons(self.choose_button, self.up_button)

        self.path_row = QWidget()
        path_layout = QHBoxLayout(self.path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.path_label, 1)

        self.search_panel = QWidget()
        search_layout = QVBoxLayout(self.search_panel)
        search_layout.setContentsMargins(_MARGIN, 0, 0, _MARGIN)
        search_layout.setSpacing(0)
        search_layout.addWidget(self.search_header)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_results, 1)

        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        # the panes meet at the splitter, so the inner edges carry no margin and
        # the gap between them is the handle alone
        left_layout.setContentsMargins(_MARGIN, _MARGIN, 0, _MARGIN)
        left_layout.setSpacing(0)
        left_layout.addWidget(self.directory_tree.header_view)
        left_layout.addWidget(self.path_row)
        left_layout.addWidget(self.directory_tree)

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
        self.setCentralWidget(self.splitter)

        self.choose_button.clicked.connect(self.choose_directory)
        self.up_button.clicked.connect(self.go_up)
        self.refresh_button.clicked.connect(self.refresh)
        # clearing the selection is what hides the label and the button: it
        # fires itemSelectionChanged, the same signal any tree click fires
        self.clear_target_button.clicked.connect(self.directory_tree.clear_subdirectory)
        self.directory_tree.itemDoubleClicked.connect(self.open_directory)
        self.directory_tree.itemSelectionChanged.connect(self._sync_creation_target)
        self.directory_tree.category_requested.connect(self.new_category)
        self.title_input.returnPressed.connect(self.create_task)
        self.create_button.clicked.connect(self.create_task)
        self.search_input.textChanged.connect(self._filter_search)
        self.search_input.returnPressed.connect(self._activate_first_search_result)
        # only a click or an activation on a result reaches the table, so
        # typing and a refill of the results never move the selection
        self.search_results.itemClicked.connect(self._activate_search_result)
        self.search_results.itemActivated.connect(self._activate_search_result)
        self.search_escape = QShortcut(
            QKeySequence(Qt.Key.Key_Escape), self.search_input
        )
        self.search_escape.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.search_escape.activated.connect(self.search_input.clear)
        self.toggle_button.clicked.connect(self.toggle_left_pane)
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
        self.setTabOrder(self.directory_tree, self.search_input)
        self.setTabOrder(self.search_input, self.search_results)
        self.setTabOrder(self.search_results, self.tabs)
        self.setTabOrder(self.tabs, self.title_input)
        self.setTabOrder(self.title_input, self.create_button)

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

    def _align_header(self) -> None:
        """Squares the headers of the window off to the tab bar height.

        The Directory and the Search header read as one set over the left
        pane, and the two titles of the preview take the same height, so
        every title the window carries reads as one set.
        """
        height = self.tabs.tabBar().sizeHint().height()
        self.directory_tree.header_view.setFixedHeight(height)
        self.search_header.setFixedHeight(height)
        self.preview_text_header.setFixedHeight(height)
        self.preview_list_header.setFixedHeight(height)

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
        """Collapses the left pane, or restores the width it had before.

        The pane is collapsed and restored through the same splitter sizes a
        drag of the handle would set, and the width to come back to is the one
        remembered at the last collapse, or the split the splitter opened with
        when the collapse came from a drag.
        """
        sizes = self.splitter.sizes()
        total = sum(sizes)

        if sizes[0] > 0:
            self._left_width = sizes[0]
            self.splitter.setSizes([0, total])
        else:
            width = self._left_width or self._initial_left_width or total
            self.splitter.setSizes([width, max(total - width, 0)])

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
        if self._initial_left_width is None:
            self._initial_left_width = self.splitter.sizes()[0]
        self._align_header()
        self._update_path_label()
        self._update_toggle_tooltip()

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
        """Returns the directory a new task is created in.

        A subdirectory selected in the tree is the target, so a task lands in a
        category without having to enter it. With the root, or nothing,
        selected the current directory is the target.

        Returns:
            The directory to create the task in.
        """
        return self._selected_directory() or self.current_directory

    def select_destination(self, category: str) -> None:
        """Selects a category in the tree, making it the creation target.

        A category heading carries the folder it stands for, so clicking one
        does what clicking that folder in the tree does: the tree keeps the
        selection, the label names it and the next task lands in it. The base
        folder heading carries the directory itself, and clicking it clears
        the tree through the same handler as the label's `x`, because no
        selection is what stands for the base folder.

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
        """Shows the preview of the selected task, or hides it with the selection.

        The preview follows the selection of the current tab through the same
        path the action bar takes, so a task row shows it and a heading, `Esc`
        or another tab hides it with no special case. Every rendering reads
        the task again, so a reload re-renders the task that is still selected,
        or hides the preview when it is gone. A closed task is read from inside
        its archive, which is never extracted: its `.md` is shown as it stands
        and the other entries are listed, while the details title says the task
        is archived and the list opens the archive itself.
        """
        panel = self.tabs.currentWidget()
        entry = (
            cast(TaskPanel, panel).listing.selected_entry()
            if panel is not None
            else None
        )

        if entry is None:
            self.preview_area.hide()
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
            self.preview_text_header,
            "Details (archived)" if archived else "Details",
        )
        self.preview_list.clear()
        for name in attachments:
            item = QListWidgetItem(name)
            # store the full path for opening; subfolders have a trailing '/'
            # and an archived task opens its whole archive instead
            path = folder if archived else folder / name.rstrip("/")
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.preview_list.addItem(item)
        self._archived_preview = archived
        self.preview_list.setToolTip(
            "Double-click opens the archive (.zip)" if archived else ""
        )
        # without attachments the list hides with the panel and its title, so
        # the text takes the full width
        self.preview_list.setVisible(bool(attachments))
        self.preview_list_panel.setVisible(bool(attachments))
        self.preview_area.show()

    def _open_attachment(self, item: QListWidgetItem) -> None:
        """Opens the attachment represented by the item.

        Checks that the path still exists on disk before opening. If it does
        not, shows a warning and refreshes the attachment list. If opening
        fails, shows a warning. An entry of a closed task opens the archive it
        stands in, with the same helper the rest of the window uses, so nothing
        is extracted and no temporary file is made.
        """
        path = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path, Path):
            return
        if not path.exists():
            QMessageBox.warning(self, "mktsk", f"Attachment no longer exists: {path}")
            self._sync_preview()
            return
        if self._archived_preview:
            try:
                helpers.open_file(path)
            except OSError as error:
                QMessageBox.warning(self, "mktsk", str(error))
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, "mktsk", f"Could not open: {path}")

    def _preview_list_key_press(self, event) -> None:
        """Handles key presses in the attachment list.

        Enter opens the selected attachment. Other keys are passed to the
        base implementation for normal navigation.
        """
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            item = self.preview_list.currentItem()
            if item is not None:
                self._open_attachment(item)
                return
        QListWidget.keyPressEvent(self.preview_list, event)

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
        self._reload_search(
            [(entry, title) for title, group in sections for entry in group.entries]
        )

    def _reload_search(self, entries: list[tuple[listing.TaskEntry, str]]) -> None:
        """Points the search panel at the tasks the listings hold.

        The results are rebuilt from the entries of one reload, closed tasks
        among them, and the query runs again over them, so a task created or
        closed since is reached the way the table now lists it.

        Args:
            entries: each listed task with the title of its category.
        """
        self._search_entries = entries
        self._filter_search()

    def _filter_search(self) -> None:
        """Refills the results with the tasks the query reaches.

        The query runs over the entries the last reload handed in, in the
        order the table lists them, and an empty query reaches nothing, so no
        hint is ever shown. The result that was highlighted is highlighted
        again when it still matches; nothing here follows a result to the
        table, so typing and a refill leave the selected task alone.
        """
        entries = [entry for entry, _ in self._search_entries]
        found = {
            entry.file
            for entry in listing.search_tasks(entries, self.search_input.text())
        }
        current = self.search_results.currentItem()
        kept = str(current.data(0, _PATH_ROLE)) if current is not None else None
        dim = self.search_results.palette().color(QPalette.ColorRole.PlaceholderText)

        self.search_results.clear()
        restored: QTreeWidgetItem | None = None

        for entry, category in self._search_entries:
            if entry.file not in found:
                continue

            row = QTreeWidgetItem(
                [_date_cell(entry), helpers.readable_title(entry.title), category]
            )
            row.setData(0, _PATH_ROLE, str(entry.file))
            row.setForeground(2, QBrush(dim))
            row.setTextAlignment(
                2,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            for column in range(3):
                row.setToolTip(column, str(entry.file))
            self.search_results.addTopLevelItem(row)
            if str(entry.file) == kept:
                restored = row

        if restored is not None:
            self.search_results.setCurrentItem(restored)

    def _activate_search_result(self, item: QTreeWidgetItem, _column: int) -> None:
        """Selects the task a search result points at, in the task table.

        The result carries the path of its task, and the table reaches the
        row from it, switching to the tab that holds the row when it sits in
        another one. Nothing here picks a category, so the destination a new
        task lands in is left where it was. A result is only on the panel
        while the listings hold the task, so the panel that holds the table
        is always there to be asked.

        Args:
            item: the result row that was clicked or activated.
            _column: the column of the row, which is never read.
        """
        self._select_task(Path(str(item.data(0, _PATH_ROLE))))

    def _select_task(self, path: Path) -> None:
        """Selects a task in the tab of the window that holds it.

        The tab that holds the row is switched to when the task is not in
        the one on show, so the selection, the action bar and the preview all
        follow it. Nothing here picks a category, so the destination a new
        task lands in is left where it was.

        Args:
            path: the .md of the task, or the archive that holds it.
        """
        panel = cast(TaskPanel, self.tabs.currentWidget())
        if panel is None:
            return

        panel.listing.select_task(path)

    def _activate_first_search_result(self) -> None:
        """Selects the first result of the search, as Return in the field asks."""
        item = self.search_results.topLevelItem(0)
        if item is not None:
            self._activate_search_result(item, 0)

    def _sections(self) -> list[tuple[str, listing.TaskGroup]]:
        """Pairs every task group with the title of its tab.

        A category without tasks, or one that holds nothing but closed tasks,
        is a group all the same, so it stands in the `All` tab as a heading of
        its own.

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
        tab.escape_shortcut.activated.connect(
            self.directory_tree.clear_subdirectory
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

    def move_task(self, folder: Path, category: Path) -> None:
        """Moves a task folder into a category and keeps the task selected.

        The folder moves whole, with the .md and every attachment it carries,
        and the task keeps its place in the history. A category that already
        holds a task of that title refuses the move, and a failure is shown in
        a `QMessageBox` like every other action, leaving the list as it was.
        Nothing is opened, and the destination a new task lands in is left
        where it was.

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
        """Returns the task a drop of files would land in.

        The files land in the folder of the selected task, so there is only a
        task when one is selected and stands as one: a closed task is an
        archive, which is never opened, so it takes nothing.

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
        """Returns the files a drag carries.

        A URL that names nothing on this machine, a page on the web say, is
        left out, so only files that can be moved are kept.

        Args:
            mime: the payload of the drag.

        Returns:
            The paths of the local files the drag carries.
        """
        if not mime.hasUrls():
            return []

        return [Path(url.toLocalFile()) for url in mime.urls() if url.toLocalFile()]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Takes in a drag of files when an open task is selected.

        The files land in the folder of the selected task, so the drag is only
        taken in when there is one to land in. A drag of anything else, of a
        task of our own for one, is left to the widget it belongs to.

        Args:
            event: the drag that entered.
        """
        if self._drop_entry() is None or not self._drop_paths(event.mimeData()):
            event.ignore()
            return

        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        """Moves the files of a drag into the folder of the selected task.

        The task keeps its place in the list, and its attachments are read
        again, so the row and the panel show what the drop brought. The
        selection does not move: the files land in the task that was already
        selected.

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

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_state()
        super().closeEvent(event)
