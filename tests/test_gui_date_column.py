"""The Date and Task cells of a task row."""

import datetime

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QStyle

from mktsk import listing
from mktsk.gui.tasklist import _COUNT_ROLE, _date_cell
from tests.gui_helpers import (
    find_task,
    painted_texts,
    row_texts,
    task_listing,
    task_panel,
)


def _task_entry(folder, title):
    """A task entry whose folder carries the given name."""
    return listing.TaskEntry(
        date=datetime.date(2099, 12, 1),
        title=title,
        file=folder / f"{title}.md",
        last_activity=datetime.date(2099, 12, 1),
        interventions=0,
        state="open",
    )


def test_the_date_cell_reads_the_date_of_a_task_folder(tmp_path):
    entry = _task_entry(tmp_path / "260918 - Foo", "Foo")

    assert _date_cell(entry) == "18/09/2026"


def test_the_date_cell_reads_a_closed_task_from_its_archive(tmp_path):
    entry = listing.TaskEntry(
        date=datetime.date(2026, 9, 18),
        title="Foo",
        file=tmp_path / "260918 - Foo.zip",
        last_activity=datetime.date(2026, 9, 18),
        interventions=0,
        state="closed",
    )

    assert _date_cell(entry) == "18/09/2026"


def test_the_date_cell_falls_back_to_the_raw_prefix(tmp_path):
    entry = _task_entry(tmp_path / "991332 - Foo", "Foo")

    assert _date_cell(entry) == "991332"


def test_a_task_row_paints_the_date_in_the_date_column(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    row = QRect(rows.visualItemRect(item))

    texts = row_texts(painted_texts(monkeypatch, rows), row)

    assert texts[0][2] == "18/09/2026"


def test_a_task_row_paints_only_the_description_in_the_task_column(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "FSociety")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    row = QRect(rows.visualItemRect(item))

    texts = row_texts(painted_texts(monkeypatch, rows), row)

    assert texts[1][2] == "F Society"
    assert "18/09/2026" not in texts[1][2]


def test_a_row_that_is_not_a_task_gets_no_date_cell(
    monkeypatch, window, tmp_path, make_task
):
    make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    heading = rows.item(0)
    row = QRect(rows.visualItemRect(heading))

    assert heading.data(_COUNT_ROLE) is None
    assert row_texts(painted_texts(monkeypatch, rows), row) == []


def test_the_date_heading_and_the_date_value_share_one_padding(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    header = task_panel(window).header
    item = find_task(window, file)
    row = QRect(rows.visualItemRect(item))
    padding = header.style().pixelMetric(QStyle.PixelMetric.PM_HeaderMargin)
    from mktsk.gui import tasklist

    texts = row_texts(painted_texts(monkeypatch, rows), row)
    expected = rows.column_rect(row, 0).left() + max(padding, tasklist._DATE_TEXT_LEFT_PADDING)
    assert texts[0][0].left() == expected
    assert header.sectionPosition(0) + max(padding, tasklist._DATE_TEXT_LEFT_PADDING) == texts[0][0].left()


def test_an_unselected_row_paints_nothing_left_of_the_date_text(
    monkeypatch, window, tmp_path, make_task
):
    file = make_task(tmp_path, "260918", "Foo")
    window.navigate_to(tmp_path)
    rows = task_listing(window)
    item = find_task(window, file)
    row = QRect(rows.visualItemRect(item))
    padding = rows.header.style().pixelMetric(QStyle.PixelMetric.PM_HeaderMargin)
    from mktsk.gui import tasklist

    texts = row_texts(painted_texts(monkeypatch, rows), row)

    assert texts
    assert (
        min(rect.left() for rect, *_ in texts)
        == rows.column_rect(row, 0).left() + max(padding, tasklist._DATE_TEXT_LEFT_PADDING)
    )
