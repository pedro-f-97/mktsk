"""The drag that moves files into the folder of the selected task."""

from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from mktsk.gui.tasklist import _ENTRY_ROLE
from mktsk.gui.window import _skipped_message
from mktsk.tasks import close_task
from tests.gui_helpers import find_task, select_tab, select_task

# the mime data of the events built here, kept alive as long as the event that
# holds it, which is what the file manager does with the one it hands over
_MIMES = []


def _mime_with_urls(urls):
    """The payload a drag carries, with the urls it names."""
    mime = QMimeData()
    mime.setUrls(urls)
    _MIMES.append(mime)
    return mime


def _mime(paths):
    """The payload a drag of files from the file manager carries."""
    return _mime_with_urls([QUrl.fromLocalFile(str(path)) for path in paths])


def _text_mime():
    """The payload of a drag that carries no file at all."""
    mime = QMimeData()
    mime.setText("just text")
    _MIMES.append(mime)
    return mime


def _drag_enter_mime(window, mime):
    """A drag entering the window, with the payload it carries."""
    event = QDragEnterEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dragEnterEvent(event)
    return event


def _drag_enter(window, paths):
    """A drag of files entering the window, as the file manager would."""
    return _drag_enter_mime(window, _mime(paths))


def _drop(window, paths):
    """A drag of files dropped on the window, as the file manager would."""
    event = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        _mime(paths),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dropEvent(event)
    return event


def test_a_drag_is_taken_in_with_an_open_task_selected(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    select_task(window, foo, "All")

    event = _drag_enter(window, [tmp_path / "note.txt"])

    assert event.isAccepted() is True


def test_a_drag_is_refused_with_no_task_selected(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)

    event = _drag_enter(window, [tmp_path / "note.txt"])

    assert event.isAccepted() is False


def test_a_drag_is_refused_with_a_closed_task_selected(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    close_task(foo.parent, "Foo")
    window.refresh()
    select_tab(window, "Closed")
    select_task(window, tmp_path / "260918 - Foo.zip", "Closed")

    # a closed task stands as an archive, which is never opened, so it takes
    # nothing
    event = _drag_enter(window, [tmp_path / "note.txt"])

    assert event.isAccepted() is False


def test_a_drag_of_something_that_is_not_local_is_refused(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    select_task(window, foo, "All")

    event = _drag_enter_mime(
        window, _mime_with_urls([QUrl("https://example.com/note.txt")])
    )

    assert event.isAccepted() is False


def test_a_drag_that_carries_no_file_is_refused(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    select_task(window, foo, "All")

    event = _drag_enter_mime(window, _text_mime())

    assert event.isAccepted() is False


def test_a_drag_is_refused_when_the_window_shows_no_task(window, tmp_path):
    window.current_directory = tmp_path / "a.md"
    window.refresh()

    event = _drag_enter(window, [tmp_path / "note.txt"])

    assert event.isAccepted() is False


def test_a_drop_moves_the_files_and_counts_them(window, tmp_path, make_task):
    foo = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    select_task(window, foo, "All")
    note = tmp_path / "note.txt"
    note.write_text("a note", encoding="utf-8")

    event = _drop(window, [note])

    assert event.isAccepted() is True
    assert (foo.parent / "note.txt").read_text(encoding="utf-8") == "a note"
    assert not note.exists()

    # the row counts the attachment the drop brought, and the panel names it
    row = find_task(window, foo, "All")
    assert row.data(_ENTRY_ROLE).attachments == 1
    assert window.preview_list.item(0).text() == "note.txt"


def test_a_drop_with_no_task_selected_moves_nothing(window, tmp_path, make_task):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    note = tmp_path / "note.txt"
    note.write_text("a note", encoding="utf-8")

    event = _drop(window, [note])

    assert event.isAccepted() is False
    assert note.exists()


def test_a_drop_with_skipped_files_warns_once(window, tmp_path, make_task, monkeypatch):
    foo = make_task(tmp_path, "260918", "Foo")
    (foo.parent / "note.txt").write_text("in the task", encoding="utf-8")
    outside = tmp_path / "note.txt"
    outside.write_text("outside", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, foo, "All")

    warned = []
    monkeypatch.setattr(window, "_warn_skipped", warned.append)

    _drop(window, [outside])

    assert len(warned) == 1
    assert warned[0] == [(outside, "already exists")]
    assert outside.exists()


def test_the_warning_names_the_files_it_left_out(
    window, tmp_path, make_task, fake_messages
):
    foo = make_task(tmp_path, "260918", "Foo")
    (foo.parent / "note.txt").write_text("in the task", encoding="utf-8")
    outside = tmp_path / "note.txt"
    outside.write_text("outside", encoding="utf-8")
    window.navigate_to(tmp_path)
    select_task(window, foo, "All")

    _drop(window, [outside])

    assert len(fake_messages["warning"]) == 1
    message = fake_messages["warning"][0]
    assert f"{outside}: already exists" in message


def test_the_warning_names_ten_files_and_counts_the_rest():
    skipped = [(Path(f"file{index}.txt"), "already exists") for index in range(12)]

    message = _skipped_message(skipped)

    assert "file9.txt: already exists" in message
    assert "file10.txt" not in message
    assert message.endswith("and 2 more")
