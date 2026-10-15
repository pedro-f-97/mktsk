"""The automatic width of the task column."""

import datetime
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QListWidgetItem

from mktsk import helpers, listing
from mktsk.gui.tasklist import (
    _COLUMN_PADDING,
    _COUNT_ROLE,
    _ENTRY_ROLE,
    _SELECTION_INDICATOR_GAP,
    _TASK_MAX_WIDTH,
    TaskListing,
    _column_widths,
)
from tests.gui_helpers import painted_texts, row_texts


def _entry(title):
    return listing.TaskEntry(
        date=datetime.date(2026, 9, 1),
        title=title,
        file=Path(title),
        last_activity=datetime.date(2026, 9, 1),
        interventions=1,
        state="open",
    )


def _add(rows, title):
    item = QListWidgetItem(helpers.readable_title(title))
    item.setData(_ENTRY_ROLE, _entry(title))
    item.setData(_COUNT_ROLE, "1")
    rows.addItem(item)
    return item


def _listing(qtbot, titles):
    """A listing of task rows with the given titles, fitted as a refresh does."""
    rows = TaskListing()
    qtbot.addWidget(rows)
    rows.resize(900, 300)
    rows.show()
    QApplication.processEvents()
    for title in titles:
        _add(rows, title)
    rows.fit_task_column()
    return rows


def _title_of_width(font, target):
    """A title whose measured width is about `target` pixels."""
    unit = QFontMetrics(font).horizontalAdvance("x")
    return "x" * max(1, target // unit)


def _title_width(item):
    """The width the description of a row needs, with its padding."""
    title = helpers.readable_title(item.data(_ENTRY_ROLE).title)
    return QFontMetrics(item.font()).horizontalAdvance(title) + 2 * _COLUMN_PADDING


def _growing_title(rows):
    """A title that lands between the default task width and the cap."""
    default = rows.header.default_task_width
    target = default + (_TASK_MAX_WIDTH - default) // 2 - _COLUMN_PADDING
    return _title_of_width(rows.font(), target)


def test_the_task_column_grows_to_fit_the_longest_description(qtbot):
    rows = _listing(qtbot, [])
    item = _add(rows, _growing_title(rows))
    rows.fit_task_column()
    header = rows.header

    assert header.default_task_width < header.sectionSize(1) < _TASK_MAX_WIDTH
    assert header.sectionSize(1) == _title_width(item)


def test_the_task_column_never_narrows_below_its_default(qtbot):
    rows = _listing(qtbot, ["tiny", "small"])

    assert rows.header.sectionSize(1) == rows.header.default_task_width


def test_a_description_past_the_cap_stops_the_column_and_elides(qtbot, monkeypatch):
    rows = _listing(qtbot, [])
    item = _add(rows, _title_of_width(rows.font(), _TASK_MAX_WIDTH + 200))
    rows.fit_task_column()

    assert rows.header.sectionSize(1) == _TASK_MAX_WIDTH
    assert _title_width(item) > _TASK_MAX_WIDTH

    painted = painted_texts(monkeypatch, rows)
    row = QRect(rows.visualItemRect(item))
    task_text = row_texts(painted, row)[1][2]
    assert task_text != helpers.readable_title(item.data(_ENTRY_ROLE).title)
    assert task_text.endswith("\N{HORIZONTAL ELLIPSIS}")


def test_a_manual_resize_of_the_task_section_survives_a_refit(qtbot):
    rows = _listing(qtbot, [])
    _add(rows, _growing_title(rows))
    rows.fit_task_column()
    rows.header.resizeSection(1, 333)

    rows.fit_task_column()

    assert rows.header.sectionSize(1) == 333


def test_the_other_sections_keep_their_defaults(qtbot):
    rows = _listing(qtbot, [])
    _add(rows, _growing_title(rows))
    rows.fit_task_column()
    header = rows.header
    columns = _column_widths()

    assert header.sectionSize(0) == columns.date
    assert header.sectionSize(3) == columns.state
    assert header.sectionSize(4) == columns.interventions
    assert header.sectionSize(5) == columns.activity


def test_the_cells_of_a_row_still_follow_the_header_at_the_fitted_width(qtbot):
    rows = _listing(qtbot, [])
    _add(rows, _growing_title(rows))
    item = _add(rows, "tiny")
    rows.fit_task_column()
    row = QRect(rows.visualItemRect(item))
    header = rows.header

    for column in range(6):
        cell = rows.column_rect(row, column)
        assert cell.left() == row.left() + header.sectionPosition(column)
        assert cell.width() == header.sectionSize(column)
    for left in range(6):
        for right in range(left + 1, 6):
            assert not rows.column_rect(row, left).intersects(
                rows.column_rect(row, right)
            )


def test_the_selected_row_still_keeps_the_selection_indicator_gap(qtbot):
    rows = _listing(qtbot, [])
    _add(rows, _growing_title(rows))
    item = _add(rows, "tiny")
    rows.fit_task_column()
    rows.setCurrentItem(item)
    row = QRect(rows.visualItemRect(item))

    selected = rows.delegate.content_rect(row, 1, True)
    plain = rows.column_rect(row, 1)
    assert selected.left() == plain.left() + rows.inset + _SELECTION_INDICATOR_GAP
