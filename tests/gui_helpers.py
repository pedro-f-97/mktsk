"""Helpers shared by the GUI test modules.

Plain functions rather than fixtures, because they read from a window that
the test already asks for and give a result straight back.
"""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPalette
from PySide6.QtWidgets import QStyleOptionViewItem

from mktsk.gui.tasklist import _ENTRY_ROLE
from mktsk.gui.tree import _PATH_ROLE


def painted_texts(monkeypatch, rows):
    """Repaints a listing, recording every text the painting draws."""
    painted = []
    original = QPainter.drawText

    def record(painter, *args):
        if len(args) == 3 and isinstance(args[0], QRect):
            painted.append((QRect(args[0]), args[1], args[2], QFont(painter.font())))
        return original(painter, *args)

    monkeypatch.setattr(QPainter, "drawText", record)
    rows.viewport().repaint()
    return painted


def row_texts(painted, row):
    """The texts painted on one row, in the order the delegate paints them."""
    return [
        (rect, flags, text, font)
        for rect, flags, text, font in painted
        if row.top() <= rect.top() < row.bottom()
    ]


def tab_index(window, title):
    for index in range(window.tabs.count()):
        if window.tabs.tabText(index) == title:
            return index
    raise AssertionError(f"there is no {title} tab")


def tab_titles(window):
    return [window.tabs.tabText(index) for index in range(window.tabs.count())]


def task_panel(window, title="All"):
    return window.tabs.widget(tab_index(window, title))


def task_listing(window, title="All"):
    return task_panel(window, title).listing


def header_labels(window, title="All"):
    """The names of the columns above a tab of tasks."""
    header = task_panel(window, title).header
    model = header.model()
    return [
        model.headerData(i, header.orientation(), Qt.ItemDataRole.DisplayRole)
        for i in range(model.columnCount() if model is not None else 0)
    ]


def tab_labels(window, title="All"):
    listing = task_listing(window, title)
    return [listing.item(index).text() for index in range(listing.count())]


def select_tab(window, title):
    window.tabs.setCurrentIndex(tab_index(window, title))


def click_heading(window, column, title="All"):
    """Clicks a column heading, which is what asks for that order."""
    task_panel(window, title).header.sectionClicked.emit(column)


def find_task(window, path, title="All"):
    listing = task_listing(window, title)
    for index in range(listing.count()):
        item = listing.item(index)
        entry = item.data(_ENTRY_ROLE)
        if entry is not None and entry.file == path:
            return item
    raise AssertionError(f"{path} is not listed in the {title} tab")


def tree_root(window):
    return window.directory_tree.topLevelItem(0)


def tree_labels(window):
    root = tree_root(window)
    if root is None:
        return []

    return [root.text(0)] + [root.child(i).text(0) for i in range(root.childCount())]


def tree_child_labels(window):
    root = tree_root(window)
    if root is None:
        return []

    return [root.child(i).text(0) for i in range(root.childCount())]


def find_directory(window, path):
    root = tree_root(window)
    for index in range(root.childCount()):
        item = root.child(index)
        if item.data(0, _PATH_ROLE) == str(path):
            return item
    raise AssertionError(f"{path} is not listed")


def select_directory(window, path):
    """Selects a category in the tree, which is what targets the creation."""
    window.directory_tree.setCurrentItem(find_directory(window, path))


def answer_dialog(monkeypatch, answer):
    """Makes the next name dialog answer with the given text."""
    monkeypatch.setattr("mktsk.gui.window.QInputDialog.getText", lambda *args: answer)


def select_task(window, path, title="All"):
    """Selects a task row, which is what brings its action bar up."""
    listing = task_listing(window, title)
    item = find_task(window, path, title)
    listing.setCurrentItem(item)
    return listing


def action_bar(window, path, title="All"):
    return select_task(window, path, title).action_bar


def render_row(view, item, state, palette=None):
    """Renders one row offscreen the way the view paints it.

    The option is filled from the item, the state is the one an unselected or
    selected row carries, and the palette is the viewport's unless the test
    hands one over. The style paints the row and the delegate paints the
    cells, so the image holds what a person sees.
    """
    rect = QRect(view.visualItemRect(item))
    palette = palette or view.viewport().palette()
    image = QImage(rect.size(), QImage.Format.Format_RGB32)
    image.fill(palette.color(QPalette.ColorRole.Base))
    index = view.indexFromItem(item)
    option = QStyleOptionViewItem()
    view.itemDelegate().initStyleOption(option, index)
    option.rect = QRect(0, 0, rect.width(), rect.height())
    option.state = state
    option.palette = palette
    option.widget = view
    painter = QPainter(image)
    view.itemDelegate().paint(painter, option, index)
    painter.end()
    return image


def row_background(image):
    """The colour most of a row is made of, which is its background."""
    counts: dict[int, int] = {}
    for y in range(image.height()):
        for x in range(image.width()):
            key = image.pixelColor(x, y).rgb()
            counts[key] = counts.get(key, 0) + 1
    return QColor(max(counts, key=counts.get))
