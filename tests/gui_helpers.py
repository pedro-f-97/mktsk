"""Helpers shared by the GUI test modules.

Plain functions rather than fixtures, because they read from a window that
the test already asks for and give a result straight back.
"""

from mktsk.gui.tasklist import _ENTRY_ROLE
from mktsk.gui.tree import _PATH_ROLE


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
    return [label.text() for label in task_panel(window, title).header.labels()]


def tab_labels(window, title="All"):
    listing = task_listing(window, title)
    return [listing.item(index).text() for index in range(listing.count())]


def select_tab(window, title):
    window.tabs.setCurrentIndex(tab_index(window, title))


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
