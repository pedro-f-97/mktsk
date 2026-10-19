"""The auxiliary row that opens below the selected task."""

import datetime
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QListWidgetItem

from mktsk import listing
from mktsk.gui.tasklist import (
    _COUNT_ROLE,
    _ENTRY_ROLE,
    _SELECTION_INDICATOR_GAP,
    TaskListing,
)
from tests.gui_helpers import (
    find_task,
    painted_texts,
    row_texts,
    select_task,
    task_listing,
)


def _cells(monkeypatch, rows, item):
    """Where every cell of a row was painted, in the order they are drawn."""
    painted = painted_texts(monkeypatch, rows)
    row = QRect(rows.visualItemRect(item))
    return [
        (rect.left(), rect.top(), rect.height(), text)
        for rect, _flags, text, _font in row_texts(painted, row)
    ]


def _listing_of(qtbot, count):
    """A listing short enough to scroll, holding plain task rows."""
    rows = TaskListing()
    qtbot.addWidget(rows)
    rows.resize(400, 60)
    rows.show()
    entry = listing.TaskEntry(
        date=datetime.date(2026, 9, 1),
        title="Task",
        file=Path("260901 - Task"),
        last_activity=datetime.date(2026, 9, 1),
        interventions=1,
        state="open",
    )
    for index in range(count):
        item = QListWidgetItem(f"18/09/2026  Task {index}")
        item.setData(_ENTRY_ROLE, entry)
        item.setData(_COUNT_ROLE, "1")
        rows.addItem(item)
    QApplication.processEvents()
    return rows


def test_selecting_a_task_paints_its_cells_where_they_were(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    plain = _cells(monkeypatch, rows, item)

    rows.setCurrentItem(item)
    selected = _cells(monkeypatch, rows, item)

    assert len(plain) == 6
    assert selected == plain


def test_an_auxiliary_row_opens_below_the_selected_task(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    plain = QRect(rows.visualItemRect(item)).height()

    rows.setCurrentItem(item)
    row = QRect(rows.visualItemRect(item))
    band_top = row.top() + rows.delegate.min_height

    assert rows.delegate.inset_row == rows.row(item)
    assert row.height() == plain + rows.delegate.accordion_height
    assert rows.action_bar.isVisible() is True
    assert rows.action_bar.geometry() == QRect(
        row.left() + _SELECTION_INDICATOR_GAP,
        band_top,
        rows.inset,
        row.bottom() - band_top + 1,
    )


def test_the_auxiliary_row_carries_the_action_icons(window, tmp_path, make_task):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = select_task(window, file)
    bar = rows.action_bar

    assert len(bar.buttons()) == 5
    for button in bar.buttons():
        assert button.isVisible()
        assert button.icon().isNull() is False


def test_the_auxiliary_row_closes_when_the_selection_goes(
    window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    plain = QRect(rows.visualItemRect(item)).height()
    rows.setCurrentItem(item)

    rows.setCurrentItem(None)

    assert rows.delegate.inset_row == -1
    assert rows.action_bar.isVisible() is False
    assert QRect(rows.visualItemRect(item)).height() == plain


def test_the_auxiliary_row_is_counted_by_the_content_height(qtbot):
    rows = _listing_of(qtbot, 30)
    plain = rows.contentsSize().height()

    rows.setCurrentRow(15)

    assert plain > 0
    assert rows.contentsSize().height() == plain + rows.delegate.accordion_height
