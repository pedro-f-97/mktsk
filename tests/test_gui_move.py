"""The drag that moves a task from one category into another."""

import shutil
from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from mktsk.gui.tasklist import _COUNT_ROLE, _MIME_TYPE
from mktsk.tasks import close_task
from tests.gui_helpers import find_task, select_tab, task_listing


def _mime(folder):
    """The payload a drag of the task in a folder carries."""
    mime = QMimeData()
    mime.setData(_MIME_TYPE, str(folder).encode())
    return mime


def _centre(listing, item):
    """The middle of a row, in the viewport."""
    return QPoint(listing.visualItemRect(item).center())


def _heading(listing, text):
    """The heading of a category, by the name it shows."""
    for index in range(listing.count()):
        item = listing.item(index)
        if item.data(_COUNT_ROLE) is None and item.text() == text:
            return item

    raise AssertionError(f"there is no {text} heading")


def _fake_drag(monkeypatch):
    """Replaces the drag of a task with one that records and never opens."""
    drags = []

    class FakeDrag:
        def __init__(self, source):
            self.source = source
            self.mime = None
            drags.append(self)

        def setMimeData(self, mime):
            self.mime = mime

        def exec(self, action):
            return action

    monkeypatch.setattr("mktsk.gui.tasklist.QDrag", FakeDrag)
    return drags


def _drop(listing, item, folder):
    """Drops the task of a folder on a row, as the view would."""
    mime = _mime(folder)
    event = QDropEvent(
        QPointF(_centre(listing, item)),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    listing.dropEvent(event)
    return event


def _drag_enter(listing, item, folder):
    """Enters a drag of the task of a folder over a row, as the view would."""
    mime = _mime(folder)
    event = QDragEnterEvent(
        _centre(listing, item),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    listing.dragEnterEvent(event)
    return event


def _drag_move(listing, item, folder):
    """Moves a drag of the task of a folder over a row, as the view would."""
    mime = _mime(folder)
    event = QDragMoveEvent(
        _centre(listing, item),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    listing.dragMoveEvent(event)
    return event


def _press(listing, item):
    """Presses a row, as a hand does."""
    QTest.mousePress(
        listing.viewport(), Qt.MouseButton.LeftButton, pos=_centre(listing, item)
    )


def _move(listing, item):
    """Moves the mouse onto a row with the button down."""
    pos = _centre(listing, item)
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(pos),
        QPointF(pos),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(listing.viewport(), event)


def test_dropping_a_task_on_a_category_moves_it(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    _drop(listing, _heading(listing, "Work"), foo.parent)

    assert (tmp_path / "Work" / "260918 - Foo").is_dir()
    assert not (tmp_path / "260918 - Foo").exists()


def test_dropping_a_task_on_an_empty_category_moves_it(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    (tmp_path / "Work").mkdir()
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    _drop(listing, _heading(listing, "Work"), foo.parent)

    assert (tmp_path / "Work" / "260918 - Foo").is_dir()
    assert not (tmp_path / "260918 - Foo").exists()


def test_dropping_a_task_on_a_task_of_another_category_moves_it(
    window, tmp_path, make_task
):
    foo = make_task(tmp_path, "260918", "Foo")
    bar = make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    _drop(listing, find_task(window, bar, "All"), foo.parent)

    assert (tmp_path / "Work" / "260918 - Foo").is_dir()
    assert not (tmp_path / "260918 - Foo").exists()


def test_dropping_a_task_in_a_tab_of_a_category_moves_it(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    bar = make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    select_tab(window, "Work")
    listing = task_listing(window, "Work")
    _drop(listing, find_task(window, bar, "Work"), foo.parent)

    assert (tmp_path / "Work" / "260918 - Foo").is_dir()
    assert not (tmp_path / "260918 - Foo").exists()


def test_dropping_a_task_on_its_own_category_does_nothing(
    window, tmp_path, make_task
):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    moved = []
    listing.move_requested.connect(
        lambda folder, category: moved.append((folder, category))
    )
    event = _drop(listing, _heading(listing, tmp_path.name), foo.parent)

    assert event.isAccepted() is False
    assert moved == []
    assert (tmp_path / "260918 - Foo").is_dir()


def test_dropping_a_task_on_a_task_of_its_own_category_does_nothing(
    window, tmp_path, make_task
):
    foo = make_task(tmp_path, "260918", "Foo")
    baz = make_task(tmp_path, "260920", "Baz")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    rows = [find_task(window, foo, "All"), find_task(window, baz, "All")]
    # the lower of the two, so the category above it is looked for past the
    # other task
    target = max(rows, key=listing.row)
    event = _drop(listing, target, foo.parent)

    assert event.isAccepted() is False
    assert (tmp_path / "260918 - Foo").is_dir()
    assert (tmp_path / "260920 - Baz").is_dir()


def test_dropping_a_task_on_the_empty_area_does_nothing(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    last = listing.item(listing.count() - 1)
    below = QPoint(5, listing.visualItemRect(last).bottom() + 5)
    mime = _mime(foo.parent)
    event = QDropEvent(
        QPointF(below),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    listing.dropEvent(event)

    assert event.isAccepted() is False
    assert (tmp_path / "260918 - Foo").is_dir()


def test_dropping_a_task_in_the_closed_tab_moves_nothing(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(foo.parent, "Foo")
    window.refresh()

    select_tab(window, "Closed")
    listing = task_listing(window, "Closed")
    closed = find_task(window, tmp_path / "260918 - Foo.zip", "Closed")
    event = _drop(listing, closed, tmp_path / "260918 - Foo")

    assert event.isAccepted() is False
    assert (tmp_path / "260918 - Foo.zip").exists()


def test_dropping_something_else_moves_nothing(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    mime = QMimeData()
    event = QDropEvent(
        QPointF(_centre(listing, _heading(listing, "Work"))),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    listing.dropEvent(event)

    assert event.isAccepted() is False
    assert not (tmp_path / "Work" / "260918 - Foo").exists()


def test_the_base_folder_is_a_category_of_its_own(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    bar = make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    _drop(listing, _heading(listing, tmp_path.name), bar.parent)

    assert (tmp_path / "260919 - Bar").is_dir()
    assert not (tmp_path / "Work" / "260919 - Bar").exists()


def test_the_moved_task_stays_selected(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    _drop(listing, _heading(listing, "Work"), foo.parent)

    entry = task_listing(window, "All").selected_entry()
    assert entry is not None
    assert entry.file == tmp_path / "Work" / "260918 - Foo" / "Foo.md"


def test_a_task_of_the_same_title_in_the_category_is_refused(
    window, tmp_path, make_task, fake_messages
):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Foo")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    _drop(listing, _heading(listing, "Work"), foo.parent)

    assert len(fake_messages["critical"]) == 1
    assert (tmp_path / "260918 - Foo").is_dir()
    assert not (tmp_path / "Work" / "260918 - Foo").exists()


def test_an_open_task_is_dragged_and_a_closed_one_is_not(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    assert find_task(window, file, "All").flags() & Qt.ItemFlag.ItemIsDragEnabled

    close_task(file.parent, "Foo")
    window.refresh()

    select_tab(window, "Closed")
    closed = task_listing(window, "Closed").item(1)
    assert not (closed.flags() & Qt.ItemFlag.ItemIsDragEnabled)


def test_a_heading_is_not_dragged(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    assert not (_heading(listing, tmp_path.name).flags() & Qt.ItemFlag.ItemIsDragEnabled)


def test_the_drag_carries_the_folder_of_the_task(
    window, tmp_path, make_task, monkeypatch
):
    foo = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    drags = _fake_drag(monkeypatch)

    listing = task_listing(window, "All")
    listing.setCurrentItem(find_task(window, foo, "All"))
    listing.startDrag(Qt.DropAction.MoveAction)

    assert len(drags) == 1
    mime = drags[0].mime
    assert Path(bytes(mime.data(_MIME_TYPE).data()).decode()) == foo.parent


def test_a_closed_task_carries_no_drag(window, tmp_path, make_task, monkeypatch):
    foo = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(foo.parent, "Foo")
    window.refresh()
    drags = _fake_drag(monkeypatch)

    select_tab(window, "Closed")
    listing = task_listing(window, "Closed")
    listing.setCurrentItem(find_task(window, tmp_path / "260918 - Foo.zip", "Closed"))
    listing.startDrag(Qt.DropAction.MoveAction)

    assert drags == []


def test_nothing_carries_no_drag(window, tmp_path, make_task, monkeypatch):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    drags = _fake_drag(monkeypatch)

    task_listing(window, "All").startDrag(Qt.DropAction.MoveAction)

    assert drags == []


def test_a_drag_over_a_category_marks_it(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    heading = _heading(listing, "Work")
    event = _drag_move(listing, heading, foo.parent)

    assert event.isAccepted() is True
    assert listing.delegate.drop_row == listing.row(heading)


def test_a_drag_over_a_task_marks_the_category_above_it(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    bar = make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    heading = _heading(listing, "Work")
    _drag_move(listing, find_task(window, bar, "All"), foo.parent)

    assert listing.delegate.drop_row == listing.row(heading)


def test_a_drag_over_the_own_category_marks_nothing(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    event = _drag_move(listing, _heading(listing, tmp_path.name), foo.parent)

    assert event.isAccepted() is False
    assert listing.delegate.drop_row == -1


def test_the_mark_goes_when_the_drag_leaves(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    _drag_move(listing, _heading(listing, "Work"), foo.parent)
    listing.dragLeaveEvent(QDragLeaveEvent())

    assert listing.delegate.drop_row == -1


def test_the_mark_goes_when_the_task_is_dropped(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    _drag_move(listing, _heading(listing, "Work"), foo.parent)
    _drop(listing, _heading(listing, "Work"), foo.parent)

    assert listing.delegate.drop_row == -1


def test_a_drag_of_a_task_is_taken_in(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path / "Work", "260919", "Bar")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    event = _drag_enter(listing, _heading(listing, "Work"), foo.parent)

    assert event.isAccepted() is True


def test_a_drag_of_something_else_is_refused(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    listing = task_listing(window, "All")
    mime = QMimeData()
    mime.setText("something else")
    event = QDragEnterEvent(
        _centre(listing, listing.item(0)),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    listing.dragEnterEvent(event)

    assert event.isAccepted() is False


def test_selecting_a_task_with_no_tab_does_nothing(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    shutil.rmtree(tmp_path)
    window.refresh()

    assert window.tabs.count() == 0

    window._select_task(file)


def test_pressing_a_closed_row_and_moving_keeps_the_selection(
    window, tmp_path, make_task
):
    foo = make_task(tmp_path, "260918", "Foo")
    bar = make_task(tmp_path, "260919", "Bar")
    window.navigate_to(tmp_path)
    close_task(foo.parent, "Foo")
    close_task(bar.parent, "Bar")
    window.refresh()

    select_tab(window, "Closed")
    listing = task_listing(window, "Closed")
    first = find_task(window, tmp_path / "260918 - Foo.zip", "Closed")
    second = find_task(window, tmp_path / "260919 - Bar.zip", "Closed")

    _press(listing, first)
    _move(listing, second)
    listing.viewport().repaint()

    assert listing.selected_entry().file == tmp_path / "260918 - Foo.zip"
    assert listing.currentItem() is first
    row = listing.visualItemRect(first)
    assert listing.action_bar.geometry().top() == row.top() + listing.delegate.min_height


def test_an_open_row_still_starts_the_drag(window, tmp_path, make_task, monkeypatch):
    foo = make_task(tmp_path, "260918", "Foo")
    make_task(tmp_path, "260919", "Bar")
    window.navigate_to(tmp_path)
    drags = _fake_drag(monkeypatch)

    listing = task_listing(window, "All")
    first = find_task(window, foo, "All")
    second = find_task(window, tmp_path / "260919 - Bar" / "Bar.md", "All")

    _press(listing, first)
    _move(listing, second)

    assert len(drags) == 1
    mime = drags[0].mime
    assert Path(bytes(mime.data(_MIME_TYPE).data()).decode()) == foo.parent
